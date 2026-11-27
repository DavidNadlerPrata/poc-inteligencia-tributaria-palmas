"""Ferramentas do assistente de IA: a camada deterministica que ele consulta.

O modelo de linguagem nunca le o banco nem os modelos de ML diretamente. Ele so
pode pedir uma destas funcoes, com argumentos validados aqui. Tres garantias
valem para todas elas e sao verificadas em tests/test_ferramentas.py:

1. Os beneficiarios do IPTU Social sao excluidos num unico lugar (`_carregar`),
   antes de qualquer calculo. A regra esta no codigo, nao no prompt: nenhuma
   instrucao dada ao assistente consegue desliga-la.
2. O banco e aberto em modo somente leitura, e a unica consulta com valor vindo
   de fora (o identificador do contribuinte) e parametrizada.
3. Toda saida e JSON simples, com numeros ja arredondados: o que o assistente
   cita na resposta e exatamente o que a ferramenta devolveu.

Nenhuma funcao aqui chama modelo de linguagem. Por isso esta camada e testada
no CI sem chave de API e sem rede.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

import config
import etl
import fairness
import modelo

ATRIBUTOS = modelo.ATRIBUTOS_CATEGORICOS + modelo.ATRIBUTOS_NUMERICOS
SETORES = [nome for nome, *_ in config.SETORES_URBANOS]
FAIXAS = ["alta", "media", "baixa"]
LIMITE_MAXIMO_FILA = 50
PADRAO_ID = re.compile(r"^[0-9a-f]{16}$")

AVISO_DADOS = ("Carteira sintetica calibrada pelos agregados oficiais da Sefin: os numeros "
               "demonstram o sistema, nao a situacao fiscal real de Palmas.")


class ErroFerramenta(ValueError):
    """Erro de uso: volta ao assistente como mensagem, para que ele corrija o pedido."""


# --------------------------------------------------------------------------
# Acesso aos dados
# --------------------------------------------------------------------------
def _conectar_somente_leitura() -> sqlite3.Connection:
    if not config.BANCO.exists():
        raise ErroFerramenta("banco de dados nao encontrado; rode python executar_poc.py")
    return sqlite3.connect(config.BANCO.resolve().as_uri() + "?mode=ro", uri=True)


def _carregar() -> tuple[pd.DataFrame, int]:
    """UNICO ponto que le a carteira. Devolve o universo de cobranca e quantos
    beneficiarios do IPTU Social ficaram de fora -- so a contagem sai daqui."""
    with contextlib.closing(_conectar_somente_leitura()) as conexao:
        carteira = pd.read_sql_query(etl.SQL_VISAO_ANALITICA, conexao)
    protegidos = carteira["iptu_social"] == 1
    return carteira[~protegidos].reset_index(drop=True), int(protegidos.sum())


def _eh_protegido(id_contribuinte: str) -> bool | None:
    """True/False conforme o cadastro; None se o identificador nao existe."""
    with contextlib.closing(_conectar_somente_leitura()) as conexao:
        linha = conexao.execute("SELECT iptu_social FROM imovel WHERE id_contribuinte = ?",
                                (id_contribuinte,)).fetchone()
    return None if linha is None else bool(linha[0])


# Cache simples: os calculos so sao refeitos quando o banco ou os modelos mudam.
_CACHE: dict = {}


def _versao() -> tuple:
    arquivos = (config.BANCO, config.MODELO_INADIMPLENCIA, config.MODELO_RECUPERABILIDADE)
    return tuple((str(a), a.stat().st_mtime_ns if a.exists() else None) for a in arquivos)


def _memo(nome: str, calcular: Callable):
    chave = (nome, _versao())
    if chave not in _CACHE:
        if len(_CACHE) > 32:
            _CACHE.clear()
        _CACHE[chave] = calcular()
    return _CACHE[chave]


def _base() -> tuple[pd.DataFrame, int]:
    """Universo de cobranca com os scores dos dois modelos e a posicao na fila."""
    def calcular():
        for caminho in (config.MODELO_INADIMPLENCIA, config.MODELO_RECUPERABILIDADE):
            if not caminho.exists():
                raise ErroFerramenta("modelos nao encontrados; rode python executar_poc.py")
        universo, excluidos = _carregar()
        universo["prob_inadimplencia"] = (joblib.load(config.MODELO_INADIMPLENCIA)
                                          .predict_proba(universo[ATRIBUTOS])[:, 1])
        fila = modelo.priorizar_cobranca(universo)
        fila["posicao_na_fila"] = np.arange(1, len(fila) + 1)
        colunas = ["id_contribuinte", "prob_recuperacao", "faixa_recuperabilidade",
                   "retorno_esperado", "posicao_na_fila"]
        return universo.merge(fila[colunas], on="id_contribuinte", how="left"), excluidos
    return _memo("base", calcular)


def _fila() -> pd.DataFrame:
    base, _ = _base()
    return base[base["posicao_na_fila"].notna()].sort_values("posicao_na_fila")


def _importancia(qual: str) -> pd.DataFrame:
    def calcular():
        base, _ = _base()
        with contextlib.redirect_stdout(io.StringIO()):
            return modelo.importancia_atributos(base, qual, n_amostra=2000)
    return _memo(f"importancia-{qual}", calcular)


def _reais(valor) -> float:
    return round(float(valor), 2)


def _prob(valor) -> float | None:
    return None if pd.isna(valor) else round(float(valor), 4)


# --------------------------------------------------------------------------
# As ferramentas
# --------------------------------------------------------------------------
def resumo_carteira() -> dict:
    base, excluidos = _base()
    fila = _fila()
    divida = fila["valor_divida_consolidada"].sum()
    retorno = fila["retorno_esperado"].sum()

    por_faixa = (fila.groupby("faixa_recuperabilidade")
                 .agg(casos=("id_contribuinte", "count"),
                      divida_reais=("valor_divida_consolidada", "sum"),
                      retorno_esperado_reais=("retorno_esperado", "sum"))
                 .reindex(FAIXAS).fillna(0).reset_index())

    return {
        "aviso": AVISO_DADOS,
        "escopo": ("Universo de cobranca: exclui os beneficiarios do IPTU Social. Por isso a "
                   "divida aqui e menor que a do cartao 'Divida ativa' da Visao Geral do "
                   "painel, que soma a carteira inteira."),
        "imoveis_no_universo_de_cobranca": len(base),
        "excluidos_por_iptu_social": excluidos,
        "imoveis_com_divida_inscrita": len(fila),
        "divida_ativa_total_reais": _reais(divida),
        "retorno_esperado_total_reais": _reais(retorno),
        "percentual_recuperavel_esperado": round(float(retorno / divida), 4) if divida else 0.0,
        "taxa_inadimplencia_observada": round(float(base["inadimplente_proximo_exercicio"].mean()), 4),
        "por_faixa_de_recuperabilidade": [
            {"faixa": linha.faixa_recuperabilidade, "casos": int(linha.casos),
             "divida_reais": _reais(linha.divida_reais),
             "retorno_esperado_reais": _reais(linha.retorno_esperado_reais)}
            for linha in por_faixa.itertuples()],
    }


def fila_cobranca(limite: int = 10, setor_urbano: str | None = None,
                  faixa_recuperabilidade: str | None = None) -> dict:
    fila = _fila()
    if setor_urbano:
        fila = fila[fila["setor_urbano"] == setor_urbano]
    if faixa_recuperabilidade:
        fila = fila[fila["faixa_recuperabilidade"] == faixa_recuperabilidade]

    return {
        "criterio": "retorno esperado = divida x probabilidade de recuperacao em 12 meses",
        "filtros": {"setor_urbano": setor_urbano, "faixa_recuperabilidade": faixa_recuperabilidade},
        "casos_que_atendem_aos_filtros": len(fila),
        "divida_dos_casos_filtrados_reais": _reais(fila["valor_divida_consolidada"].sum()),
        "retorno_esperado_dos_casos_filtrados_reais": _reais(fila["retorno_esperado"].sum()),
        "primeiros_casos": [
            {"posicao_na_fila_geral": int(linha.posicao_na_fila),
             "id_contribuinte": linha.id_contribuinte,
             "setor_urbano": linha.setor_urbano,
             "tipo_imovel": linha.tipo_imovel,
             "divida_reais": _reais(linha.valor_divida_consolidada),
             "dias_de_inadimplencia": int(linha.tempo_inadimplencia_dias),
             "prob_recuperacao": _prob(linha.prob_recuperacao),
             "faixa_recuperabilidade": linha.faixa_recuperabilidade,
             "retorno_esperado_reais": _reais(linha.retorno_esperado)}
            for linha in fila.head(limite).itertuples()],
        "observacao": "A fila ordena o trabalho do servidor; nao e decisao de cobranca.",
    }


def indicadores_por(dimensao: str) -> dict:
    base, _ = _base()
    if dimensao == "faixa_recuperabilidade":
        base = base[base["faixa_recuperabilidade"].notna()]

    grupos = (base.groupby(dimensao)
              .agg(imoveis=("id_contribuinte", "count"),
                   taxa_inadimplencia_observada=("inadimplente_proximo_exercicio", "mean"),
                   prob_media_inadimplencia=("prob_inadimplencia", "mean"),
                   com_divida=("valor_divida_consolidada", lambda s: int((s > 0).sum())),
                   divida_reais=("valor_divida_consolidada", "sum"),
                   retorno_esperado_reais=("retorno_esperado", "sum"))
              .sort_values("divida_reais", ascending=False).reset_index())

    return {
        "dimensao": dimensao,
        "grupos": [
            {dimensao: linha[dimensao],
             "imoveis": int(linha["imoveis"]),
             "taxa_inadimplencia_observada": round(float(linha["taxa_inadimplencia_observada"]), 4),
             "prob_media_inadimplencia_prevista": round(float(linha["prob_media_inadimplencia"]), 4),
             "imoveis_com_divida": int(linha["com_divida"]),
             "divida_reais": _reais(linha["divida_reais"]),
             "retorno_esperado_reais": _reais(linha["retorno_esperado_reais"])}
            for _, linha in grupos.iterrows()],
    }


def consultar_contribuinte(id_contribuinte: str) -> dict:
    protegido = _eh_protegido(id_contribuinte)
    if protegido is None:
        raise ErroFerramenta(f"contribuinte {id_contribuinte} nao encontrado no cadastro")
    if protegido:
        return {"id_contribuinte": id_contribuinte,
                "no_universo_de_cobranca": False,
                "motivo": ("Fora do universo de cobranca por regra de protecao legal. O sistema "
                           "nao emite score nem informa dados deste contribuinte.")}

    base, _ = _base()
    linha = base[base["id_contribuinte"] == id_contribuinte].iloc[0]
    tem_divida = linha["valor_divida_consolidada"] > 0
    qual = "recuperabilidade" if tem_divida else "inadimplencia"
    referencia = base[base["valor_divida_consolidada"] > 0] if tem_divida else base

    comparacao = []
    for atributo in _importancia(qual)["atributo"]:
        if atributo not in modelo.ATRIBUTOS_NUMERICOS:
            continue
        valor = float(linha[atributo])
        comparacao.append({
            "atributo": atributo,
            "valor_do_contribuinte": round(valor, 2),
            "mediana_da_referencia": round(float(referencia[atributo].median()), 2),
            "percentual_da_referencia_abaixo_dele": round(float((referencia[atributo] < valor).mean()), 4),
        })
        if len(comparacao) == 5:
            break

    return {
        "id_contribuinte": id_contribuinte,
        "no_universo_de_cobranca": True,
        "elegibilidade": ("Verificado no cadastro antes desta consulta: nao e beneficiario do "
                          "IPTU Social, portanto pode figurar na fila de cobranca."),
        "setor_urbano": linha["setor_urbano"],
        "tipo_imovel": linha["tipo_imovel"],
        "valor_venal_reais": _reais(linha["valor_venal"]),
        "divida_reais": _reais(linha["valor_divida_consolidada"]),
        "dias_de_inadimplencia": int(linha["tempo_inadimplencia_dias"]),
        "prob_inadimplencia_proximo_exercicio": _prob(linha["prob_inadimplencia"]),
        "prob_recuperacao_12_meses": _prob(linha["prob_recuperacao"]),
        "faixa_recuperabilidade": linha["faixa_recuperabilidade"] if tem_divida else None,
        "retorno_esperado_reais": _reais(linha["retorno_esperado"]) if tem_divida else 0.0,
        "posicao_na_fila": int(linha["posicao_na_fila"]) if tem_divida else None,
        "total_na_fila": len(_fila()),
        "comparacao_com_a_carteira": {
            "modelo_de_referencia": qual,
            "referencia": ("contribuintes com divida inscrita" if tem_divida
                           else "todo o universo de cobranca"),
            "atributos_mais_importantes_do_modelo": comparacao,
        },
        "como_ler": ("Os atributos sao os mais importantes para o modelo na carteira toda "
                     "(importancia por permutacao). A comparacao com a mediana mostra onde este "
                     "contribuinte se situa; nao e uma decomposicao exata da nota individual."),
    }


def importancia_atributos(modelo_avaliado: str = "recuperabilidade") -> dict:
    tabela = _importancia(modelo_avaliado)
    return {
        "modelo": modelo_avaliado,
        "metodo": ("importancia por permutacao: queda do ROC-AUC quando o atributo e "
                   "embaralhado. Valores perto de zero indicam atributo pouco usado."),
        "atributos": [{"atributo": a, "importancia": round(float(v), 4)}
                      for a, v in zip(tabela["atributo"], tabela["importancia"], strict=True)],
        "observacao": ("Na carteira sintetica, a importancia reflete o processo que gerou os "
                       "dados, nao uma relacao causal do mundo real."),
    }


def auditoria_equidade(modelo_avaliado: str = "recuperabilidade") -> dict:
    caminho = config.DADOS / f"teste_{modelo_avaliado}.csv"
    if not caminho.exists():
        raise ErroFerramenta("conjunto de teste nao encontrado; rode python executar_poc.py")
    with contextlib.redirect_stdout(io.StringIO()):
        laudo = fairness.auditar(pd.read_csv(caminho, sep=";"))
    return {
        "modelo": modelo_avaliado,
        "grupo_protegido": "faixa de renda predominante do setor urbano",
        "limiar_de_alerta": fairness.LIMIAR_ALERTA,
        "por_grupo": laudo["por_grupo"],
        "paridade_demografica": laudo["paridade_demografica"],
        "igualdade_de_oportunidade": laudo["igualdade_oportunidade"],
        "onde_ha_discussao": "docs/RIA.md, secao 2 (vieses e mitigacao)",
    }


def desempenho_modelos() -> dict:
    if not config.METRICAS.exists():
        raise ErroFerramenta("metricas nao encontradas; rode python executar_poc.py")
    metricas = json.loads(config.METRICAS.read_text(encoding="utf-8"))
    return {
        "metricas_no_conjunto_de_teste": metricas,
        "metodologia": ("Pipeline de demonstracao: split aleatorio estratificado, 25% para "
                        "teste. A metodologia com split temporal esta na aula da Sprint 4."),
        "como_ler": ("ROC-AUC 0,5 e o acaso e 1,0 e perfeito. Valores moderados sao esperados "
                     "numa carteira com ruido deliberado; valores perto de 1,0 indicariam "
                     "vazamento de dados."),
    }


# --------------------------------------------------------------------------
# Registro: nome, descricao e esquema que o modelo de linguagem enxerga
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict
    funcao: Callable[..., dict]

    def esquema(self) -> dict:
        """Formato de ferramenta da API de chat (OpenAI/OpenRouter)."""
        return {"type": "function",
                "function": {"name": self.nome, "description": self.descricao,
                             "parameters": self.parametros}}


def _objeto(propriedades: dict | None = None, obrigatorios: list | None = None) -> dict:
    return {"type": "object", "properties": propriedades or {},
            "required": obrigatorios or [], "additionalProperties": False}


_MODELO_AVALIADO = {"type": "string", "enum": ["recuperabilidade", "inadimplencia"],
                    "description": "Modelo 2 (recuperabilidade, ordena a fila) ou "
                                   "Modelo 1 (inadimplencia no proximo exercicio)."}

FERRAMENTAS: dict[str, Ferramenta] = {f.nome: f for f in [
    Ferramenta(
        "resumo_carteira",
        "Panorama da carteira: tamanho do universo de cobranca, divida ativa total, retorno "
        "esperado, taxa de inadimplencia e distribuicao por faixa de recuperabilidade.",
        _objeto(), resumo_carteira),
    Ferramenta(
        "fila_cobranca",
        "Fila de cobranca ordenada por retorno esperado (divida x probabilidade de "
        "recuperacao). Aceita filtro por setor urbano e por faixa de recuperabilidade.",
        _objeto({
            "limite": {"type": "integer", "minimum": 1, "maximum": LIMITE_MAXIMO_FILA,
                       "description": "Quantos casos listar (padrao 10)."},
            "setor_urbano": {"type": "string", "enum": SETORES},
            "faixa_recuperabilidade": {"type": "string", "enum": FAIXAS},
        }), fila_cobranca),
    Ferramenta(
        "indicadores_por",
        "Indicadores agregados por grupo: imoveis, taxa de inadimplencia observada e prevista, "
        "divida e retorno esperado.",
        _objeto({"dimensao": {"type": "string",
                              "enum": ["setor_urbano", "tipo_imovel", "faixa_renda_setor",
                                       "faixa_recuperabilidade"]}},
                ["dimensao"]), indicadores_por),
    Ferramenta(
        "consultar_contribuinte",
        "Dados, scores e posicao na fila de UM contribuinte, pelo identificador "
        "pseudonimizado (16 caracteres hexadecimais), com a comparacao dos atributos mais "
        "importantes com a mediana da carteira -- base para explicar a classificacao.",
        _objeto({"id_contribuinte": {"type": "string", "pattern": PADRAO_ID.pattern}},
                ["id_contribuinte"]), consultar_contribuinte),
    Ferramenta(
        "importancia_atributos",
        "Quais atributos mais pesam para o modelo, por importancia por permutacao.",
        _objeto({"modelo_avaliado": _MODELO_AVALIADO}), importancia_atributos),
    Ferramenta(
        "auditoria_equidade",
        "Auditoria de fairness por faixa de renda do setor: taxa de selecao e recall por grupo, "
        "paridade demografica e igualdade de oportunidade, com o limiar de alerta de 0,10.",
        _objeto({"modelo_avaliado": _MODELO_AVALIADO}), auditoria_equidade),
    Ferramenta(
        "desempenho_modelos",
        "Metricas de teste dos dois modelos: acuracia, precisao, recall, F1, ROC-AUC e "
        "matriz de confusao.",
        _objeto(), desempenho_modelos),
]}


def esquemas() -> list[dict]:
    return [f.esquema() for f in FERRAMENTAS.values()]


# --------------------------------------------------------------------------
# Validacao e execucao
# --------------------------------------------------------------------------
def _validar(esquema: dict, argumentos) -> dict:
    """Confere os argumentos contra o esquema. Valores nulos contam como omitidos."""
    if not isinstance(argumentos, dict):
        raise ErroFerramenta("os argumentos devem ser um objeto JSON")
    argumentos = {k: v for k, v in argumentos.items() if v is not None}
    propriedades = esquema["properties"]

    sobrando = set(argumentos) - set(propriedades)
    if sobrando:
        raise ErroFerramenta(f"argumentos nao aceitos: {sorted(sobrando)}")
    faltando = [p for p in esquema["required"] if p not in argumentos]
    if faltando:
        raise ErroFerramenta(f"argumentos obrigatorios ausentes: {faltando}")

    for nome, valor in argumentos.items():
        regra = propriedades[nome]
        if regra["type"] == "integer":
            if isinstance(valor, float) and valor.is_integer():
                valor = argumentos[nome] = int(valor)
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise ErroFerramenta(f"'{nome}' deve ser inteiro")
            if not regra.get("minimum", -math.inf) <= valor <= regra.get("maximum", math.inf):
                raise ErroFerramenta(f"'{nome}' deve estar entre {regra.get('minimum')} "
                                     f"e {regra.get('maximum')}")
        elif regra["type"] == "string" and not isinstance(valor, str):
            raise ErroFerramenta(f"'{nome}' deve ser texto")
        if "enum" in regra and valor not in regra["enum"]:
            raise ErroFerramenta(f"'{nome}' deve ser um destes valores: {regra['enum']}")
        if "pattern" in regra and not re.fullmatch(regra["pattern"], valor):
            raise ErroFerramenta(f"'{nome}' fora do formato esperado")
    return argumentos


def _json_simples(objeto):
    """Converte tipos do numpy/pandas e troca NaN por null."""
    if isinstance(objeto, dict):
        return {str(k): _json_simples(v) for k, v in objeto.items()}
    if isinstance(objeto, list | tuple):
        return [_json_simples(v) for v in objeto]
    if isinstance(objeto, np.bool_):
        return bool(objeto)
    if isinstance(objeto, np.integer):
        return int(objeto)
    if isinstance(objeto, float | np.floating):
        return None if math.isnan(objeto) else float(objeto)
    return objeto


def executar(nome: str, argumentos) -> dict:
    """Ponto unico de execucao. Nunca levanta excecao: erros voltam como {'erro': ...}."""
    ferramenta = FERRAMENTAS.get(nome)
    if ferramenta is None:
        return {"erro": f"ferramenta desconhecida: {nome}. Disponiveis: {sorted(FERRAMENTAS)}"}
    try:
        validos = _validar(ferramenta.parametros, argumentos)
        return _json_simples(ferramenta.funcao(**validos))
    except ErroFerramenta as erro:
        return {"erro": str(erro)}
    except Exception as erro:  # noqa: BLE001 -- detalhe interno nao vai para o modelo
        return {"erro": f"falha interna ao executar {nome} ({type(erro).__name__})"}
