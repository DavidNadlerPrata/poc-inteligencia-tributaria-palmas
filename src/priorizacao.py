"""Avaliacao da fila de cobranca antes de adota-la.

Duas perguntas que a Sefin deve fazer a qualquer fila ordenada por modelo:

1. Ela recupera mais do que uma regra simples, como "maiores dividas primeiro"?
   A comparacao usa o conjunto de teste do Modelo 2 -- dividas que o modelo
   nao viu no treino -- e o valor DE FATO recuperado, nao o estimado.

2. Ela deixa dividas prescreverem? A acao de cobranca do credito tributario
   prescreve em cinco anos (CTN, art. 174). Uma fila por retorno esperado
   empurra para o fim as dividas antigas, que o modelo ve como pouco
   recuperaveis -- justamente as mais perto de prescrever.

Limite do alerta de prescricao: o tempo de inadimplencia e usado como
aproximacao do tempo desde a constituicao definitiva do credito, e a carteira
nao registra as causas que interrompem a prescricao (parcelamento, protesto,
despacho que ordena a citacao na execucao fiscal). O alerta indica o que
conferir; a situacao juridica de cada divida e decisao da Procuradoria.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PRAZO_PRESCRICAO_ANOS = 5      # CTN, art. 174
JANELA_DE_ALERTA_ANOS = 1
DIAS_POR_ANO = 365.25

ALERTA_PROXIMA = "prescreve em até 12 meses"
ALERTA_VENCIDA = "5 anos ou mais: verificar prescrição"

ORDENACOES = {
    "modelo": "Modelo 2: dívida × probabilidade",
    "maiores_dividas": "Maiores dívidas primeiro",
    "mais_recentes": "Mais recentes primeiro",
    "probabilidade": "Só a probabilidade do modelo",
}
FRACOES_RESUMO = (0.10, 0.20, 0.30, 0.50)


# --------------------------------------------------------------------------
# Prescricao
# --------------------------------------------------------------------------
def alerta_prescricao(dias_de_inadimplencia: pd.Series) -> pd.Series:
    """Alerta por divida: vazio, proxima de prescrever ou com 5 anos ou mais."""
    anos = dias_de_inadimplencia / DIAS_POR_ANO
    alerta = np.select(
        [anos >= PRAZO_PRESCRICAO_ANOS,
         anos >= PRAZO_PRESCRICAO_ANOS - JANELA_DE_ALERTA_ANOS],
        [ALERTA_VENCIDA, ALERTA_PROXIMA], default="")
    return pd.Series(alerta, index=dias_de_inadimplencia.index)


def resumo_prescricao(fila: pd.DataFrame, fracao_topo: float = 0.20) -> dict:
    """Quantas dividas de cada alerta existem e onde elas caem na fila.

    A fila precisa estar na ordem de trabalho (a de priorizar_cobranca).
    """
    alertas = alerta_prescricao(fila["tempo_inadimplencia_dias"]).to_numpy()
    posicao = np.arange(1, len(fila) + 1) / len(fila)
    resumo = {}
    for alerta in (ALERTA_PROXIMA, ALERTA_VENCIDA):
        marca = alertas == alerta
        divida_do_alerta = float(fila.loc[marca, "valor_divida_consolidada"].sum())
        divida_da_fila = float(fila["valor_divida_consolidada"].sum())
        resumo[alerta] = {
            "casos": int(marca.sum()),
            "divida_reais": round(divida_do_alerta, 2),
            # Percentuais prontos e com a base no nome: quem le (pessoa ou
            # assistente de IA) nao precisa adivinhar sobre o que foram calculados.
            "percentual_dos_casos_da_fila": round(float(marca.mean()), 4),
            "percentual_da_divida_da_fila": (round(divida_do_alerta / divida_da_fila, 4)
                                             if divida_da_fila else 0.0),
            f"no_topo_{int(fracao_topo * 100)}pct": int((marca & (posicao <= fracao_topo)).sum()),
            "posicao_mediana_na_fila": (round(float(np.median(posicao[marca])), 4)
                                        if marca.any() else None),
        }
    return resumo


# --------------------------------------------------------------------------
# Comparacao com regras simples
# --------------------------------------------------------------------------
def _chave_de_ordenacao(teste: pd.DataFrame, nome: str) -> pd.Series:
    divida = teste["valor_divida_consolidada"]
    if nome == "modelo":
        return divida * teste["y_prob"]
    if nome == "maiores_dividas":
        return divida
    if nome == "mais_recentes":
        return -teste["tempo_inadimplencia_dias"]
    if nome == "probabilidade":
        return teste["y_prob"]
    raise ValueError(f"ordenacao desconhecida: {nome}")


def _captura_acumulada(teste: pd.DataFrame, nome: str) -> np.ndarray:
    """Fracao do valor recuperado alcancada ao trabalhar os k primeiros casos."""
    recuperado = (teste["valor_divida_consolidada"] * teste["y_real"]).to_numpy()
    ordem = np.argsort(-_chave_de_ordenacao(teste, nome).to_numpy(), kind="mergesort")
    return np.cumsum(recuperado[ordem]) / recuperado.sum()


def _na_fracao(acumulada: np.ndarray, fracao: float) -> float:
    k = max(1, int(round(len(acumulada) * fracao)))
    return float(acumulada[k - 1])


def curvas_de_captura(teste: pd.DataFrame, pontos: int = 100) -> pd.DataFrame:
    """Curva de cada ordenacao: % dos casos trabalhados x % do valor recuperado.

    `teste` precisa de valor_divida_consolidada, tempo_inadimplencia_dias,
    y_prob (probabilidade do Modelo 2) e y_real (recuperou ou nao). Uma divida
    recuperada conta pelo valor inteiro: o alvo e binario.
    """
    fracoes = np.linspace(0, 1, pontos + 1)
    curvas = {"fracao_casos": fracoes, "aleatoria": fracoes}
    for nome in ORDENACOES:
        acumulada = _captura_acumulada(teste, nome)
        curvas[nome] = [0.0] + [_na_fracao(acumulada, f) for f in fracoes[1:]]
    return pd.DataFrame(curvas).round(4)


def resumo_comparacao(teste: pd.DataFrame) -> dict:
    """Valor recuperado alcancado por cada ordenacao em alguns pontos da fila."""
    return {nome: {f"{int(f * 100)}pct": round(_na_fracao(_captura_acumulada(teste, nome), f), 4)
                   for f in FRACOES_RESUMO}
            for nome in ORDENACOES}


def diferenca_bootstrap(teste: pd.DataFrame, a: str = "modelo", b: str = "maiores_dividas",
                        fracao: float = 0.20, n_reamostras: int = 1000,
                        semente: int = 42) -> dict:
    """Diferenca de captura entre duas ordenacoes, com IC de 95% por bootstrap."""
    def diferenca(amostra):
        return (_na_fracao(_captura_acumulada(amostra, a), fracao)
                - _na_fracao(_captura_acumulada(amostra, b), fracao))

    rng = np.random.default_rng(semente)
    reamostras = [diferenca(teste.iloc[rng.integers(0, len(teste), len(teste))])
                  for _ in range(n_reamostras)]
    return {"comparacao": f"{a} - {b}", "fracao_da_fila": fracao,
            "diferenca": round(diferenca(teste), 4),
            "ic_inferior": round(float(np.percentile(reamostras, 2.5)), 4),
            "ic_superior": round(float(np.percentile(reamostras, 97.5)), 4)}


def comparar_ordenacoes(teste: pd.DataFrame) -> dict:
    """Tudo o que o pipeline grava e o painel mostra."""
    recuperado = (teste["valor_divida_consolidada"] * teste["y_real"]).sum()
    return {
        "rotulos": ORDENACOES,
        "n_casos": len(teste),
        "valor_recuperado_reais": round(float(recuperado), 2),
        "premissa": ("Conjunto de teste do Modelo 2. Uma divida recuperada conta pelo "
                     "valor inteiro, porque o alvo e binario."),
        "resumo": resumo_comparacao(teste),
        "diferenca_modelo_x_maiores_dividas": diferenca_bootstrap(teste),
        "curvas": curvas_de_captura(teste).to_dict("list"),
    }
