"""Testes da camada de ferramentas do assistente de IA (src/ferramentas.py).

O modelo de linguagem so enxerga os dados por estas funcoes. Por isso as regras
que nao podem falhar sao testadas aqui, e nao no comportamento do modelo:
nenhum texto digitado no chat consegue mudar o que estas funcoes devolvem.

Rodam sem rede e sem chave de API.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import sqlite3

import pytest

import config
import ferramentas
import modelo


def _todas_as_saidas(ids_para_consultar: list[str]) -> list[dict]:
    """Chama cada ferramenta com todas as combinacoes de argumentos enumeraveis."""
    saidas = [ferramentas.executar("resumo_carteira", {}),
              ferramentas.executar("desempenho_modelos", {})]
    for setor, faixa in itertools.product([None, *ferramentas.SETORES],
                                          [None, *ferramentas.FAIXAS]):
        saidas.append(ferramentas.executar("fila_cobranca", {
            "limite": ferramentas.LIMITE_MAXIMO_FILA, "setor_urbano": setor,
            "faixa_recuperabilidade": faixa}))
    dimensoes = ferramentas.FERRAMENTAS["indicadores_por"].parametros["properties"]["dimensao"]["enum"]
    saidas += [ferramentas.executar("indicadores_por", {"dimensao": d}) for d in dimensoes]
    for qual in ("recuperabilidade", "inadimplencia"):
        saidas.append(ferramentas.executar("importancia_atributos", {"modelo_avaliado": qual}))
        saidas.append(ferramentas.executar("auditoria_equidade", {"modelo_avaliado": qual}))
    saidas += [ferramentas.executar("consultar_contribuinte", {"id_contribuinte": i})
               for i in ids_para_consultar]
    return saidas


@pytest.fixture(scope="module")
def protegidos(ambiente_treinado) -> set[str]:
    base = ambiente_treinado["base"]
    return set(base.loc[base["iptu_social"] == 1, "id_contribuinte"])


class TestIptuSocialForaDasFerramentas:
    """Regra legal (secao 11 do plano de ensino; RIA, secao 2.4) aplicada ao assistente."""

    def test_carteira_de_teste_tem_beneficiarios(self, protegidos):
        """Guarda contra falso positivo: sem beneficiarios, os testes abaixo nao provam nada."""
        assert len(protegidos) > 0

    def test_base_interna_nao_contem_beneficiarios(self, protegidos):
        base, _ = ferramentas._base()
        assert (base["iptu_social"] == 0).all()
        assert not protegidos & set(base["id_contribuinte"])

    def test_nenhuma_saida_cita_um_beneficiario(self, ambiente_treinado, protegidos):
        fila = ferramentas._fila()
        elegiveis = fila["id_contribuinte"].head(30).tolist()
        sem_divida = ferramentas._base()[0].query("valor_divida_consolidada == 0")
        elegiveis += sem_divida["id_contribuinte"].head(5).tolist()

        texto = json.dumps(_todas_as_saidas(elegiveis), ensure_ascii=False)
        vazados = [p for p in protegidos if p in texto]
        assert not vazados, f"{len(vazados)} beneficiarios do IPTU Social nas saidas"
        assert '"erro"' not in texto

    def test_consulta_a_beneficiario_nao_devolve_dados(self, protegidos):
        alvo = sorted(protegidos)[0]
        resultado = ferramentas.executar("consultar_contribuinte", {"id_contribuinte": alvo})
        assert resultado["no_universo_de_cobranca"] is False
        assert set(resultado) == {"id_contribuinte", "no_universo_de_cobranca", "motivo"}

    def test_contagem_de_excluidos_bate_com_o_cadastro(self, ambiente_treinado, protegidos):
        resumo = ferramentas.executar("resumo_carteira", {})
        assert resumo["excluidos_por_iptu_social"] == len(protegidos)
        assert (resumo["imoveis_no_universo_de_cobranca"]
                == len(ambiente_treinado["base"]) - len(protegidos))


class TestSomenteLeitura:

    def test_banco_recusa_escrita(self, ambiente_treinado):
        with contextlib.closing(ferramentas._conectar_somente_leitura()) as conexao:
            with pytest.raises(sqlite3.OperationalError):
                conexao.execute("DELETE FROM imovel")

    def test_banco_continua_intacto(self, ambiente_treinado):
        with contextlib.closing(ferramentas._conectar_somente_leitura()) as conexao:
            total = conexao.execute("SELECT COUNT(*) FROM imovel").fetchone()[0]
        assert total == len(ambiente_treinado["base"])

    @pytest.mark.parametrize("tentativa", [
        "x' OR '1'='1",
        "0000000000000000; DROP TABLE imovel",
        "../../etc/passwd",
    ])
    def test_identificador_malicioso_e_barrado_na_validacao(self, ambiente_treinado, tentativa):
        resultado = ferramentas.executar("consultar_contribuinte", {"id_contribuinte": tentativa})
        assert "erro" in resultado


class TestValidacaoDosArgumentos:

    @pytest.mark.parametrize("nome, argumentos, trecho", [
        ("apagar_banco", {}, "desconhecida"),
        ("fila_cobranca", {"limite": 0}, "entre"),
        ("fila_cobranca", {"limite": ferramentas.LIMITE_MAXIMO_FILA + 1}, "entre"),
        ("fila_cobranca", {"limite": "10"}, "inteiro"),
        ("fila_cobranca", {"limite": True}, "inteiro"),
        ("fila_cobranca", {"setor_urbano": "Bairro Inexistente"}, "valores"),
        ("fila_cobranca", {"ordenar_por": "renda"}, "nao aceitos"),
        ("indicadores_por", {}, "obrigatorios"),
        ("indicadores_por", {"dimensao": "iptu_social"}, "valores"),
        ("resumo_carteira", ["lista"], "objeto"),
    ])
    def test_argumento_invalido_vira_erro_legivel(self, ambiente_treinado, nome, argumentos, trecho):
        resultado = ferramentas.executar(nome, argumentos)
        assert set(resultado) == {"erro"}
        assert trecho in resultado["erro"]

    def test_nulo_conta_como_omitido(self, ambiente_treinado):
        resultado = ferramentas.executar("fila_cobranca", {"limite": 3, "setor_urbano": None})
        assert len(resultado["primeiros_casos"]) == 3

    def test_inteiro_vindo_como_float_e_aceito(self, ambiente_treinado):
        resultado = ferramentas.executar("fila_cobranca", {"limite": 4.0})
        assert len(resultado["primeiros_casos"]) == 4

    def test_falha_interna_nao_vaza_detalhe(self, ambiente_treinado, monkeypatch):
        def quebrada():
            raise RuntimeError("caminho/secreto/no/servidor")

        original = ferramentas.FERRAMENTAS["resumo_carteira"]
        monkeypatch.setitem(ferramentas.FERRAMENTAS, "resumo_carteira",
                            ferramentas.Ferramenta(original.nome, original.descricao,
                                                   original.parametros, quebrada))
        resultado = ferramentas.executar("resumo_carteira", {})
        assert "RuntimeError" in resultado["erro"]
        assert "secreto" not in resultado["erro"]

    def test_sem_banco_a_mensagem_orienta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "BANCO", tmp_path / "inexistente.db")
        resultado = ferramentas.executar("resumo_carteira", {})
        assert "executar_poc.py" in resultado["erro"]


class TestContrato:
    """O que o modelo de linguagem recebe precisa ser estavel e bem formado."""

    @pytest.mark.parametrize("nome", sorted(ferramentas.FERRAMENTAS))
    def test_esquema_bem_formado(self, nome):
        esquema = ferramentas.FERRAMENTAS[nome].esquema()
        funcao = esquema["function"]
        assert esquema["type"] == "function" and funcao["name"] == nome
        assert len(funcao["description"]) > 30
        parametros = funcao["parameters"]
        assert parametros["additionalProperties"] is False
        assert set(parametros["required"]) <= set(parametros["properties"])

    def test_saidas_sao_json_estrito(self, ambiente_treinado):
        """allow_nan=False: NaN nao e JSON valido e quebraria a conversa com o modelo."""
        primeiro = ferramentas._fila()["id_contribuinte"].iloc[0]
        for saida in _todas_as_saidas([primeiro]):
            json.dumps(saida, allow_nan=False)

    def test_fila_coincide_com_a_do_pipeline(self, ambiente_treinado):
        """O assistente e o painel precisam contar a mesma historia."""
        do_pipeline = modelo.priorizar_cobranca(ambiente_treinado["base"])
        resumo = ferramentas.executar("resumo_carteira", {})
        assert resumo["imoveis_com_divida_inscrita"] == len(do_pipeline)
        assert resumo["retorno_esperado_total_reais"] == pytest.approx(
            do_pipeline["retorno_esperado"].sum(), abs=0.05)

        fila = ferramentas.executar("fila_cobranca", {"limite": 5})["primeiros_casos"]
        assert [c["id_contribuinte"] for c in fila] == do_pipeline["id_contribuinte"].head(5).tolist()

    def test_fila_ordenada_por_retorno(self, ambiente_treinado):
        casos = ferramentas.executar("fila_cobranca", {"limite": 50})["primeiros_casos"]
        retornos = [c["retorno_esperado_reais"] for c in casos]
        assert retornos == sorted(retornos, reverse=True)
        assert [c["posicao_na_fila_geral"] for c in casos] == list(range(1, 51))

    def test_filtro_respeitado(self, ambiente_treinado):
        resultado = ferramentas.executar("fila_cobranca", {
            "limite": 50, "setor_urbano": "Taquaralto", "faixa_recuperabilidade": "alta"})
        assert resultado["casos_que_atendem_aos_filtros"] > 0
        assert all(c["setor_urbano"] == "Taquaralto" and c["faixa_recuperabilidade"] == "alta"
                   for c in resultado["primeiros_casos"])

    def test_contribuinte_sem_divida_fica_fora_da_fila(self, ambiente_treinado):
        base, _ = ferramentas._base()
        alvo = base.loc[base["valor_divida_consolidada"] == 0, "id_contribuinte"].iloc[0]
        resultado = ferramentas.executar("consultar_contribuinte", {"id_contribuinte": alvo})
        assert resultado["posicao_na_fila"] is None
        assert resultado["prob_recuperacao_12_meses"] is None
        assert resultado["comparacao_com_a_carteira"]["modelo_de_referencia"] == "inadimplencia"

    def test_identificador_inexistente(self, ambiente_treinado):
        resultado = ferramentas.executar("consultar_contribuinte",
                                         {"id_contribuinte": "0" * 16})
        assert "nao encontrado" in resultado["erro"]
