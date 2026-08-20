"""Auditoria de justica algoritmica (Sprint 4 - Modulo 7).

Implementa os dois testes exigidos pelo plano de ensino, sem dependencia
externa -- as formulas sao curtas e explicita-las tem valor pedagogico.

1. Paridade Demografica (Demographic Parity)
   Compara P(Y_pred = 1 | A = a) entre grupos. Mede se o sistema seleciona
   pessoas na mesma proporcao, independentemente do grupo protegido.
       DPD = max_a P(Y_pred=1|A=a) - min_a P(Y_pred=1|A=a)

2. Igualdade de Oportunidade (Equal Opportunity)
   Compara P(Y_pred = 1 | Y = 1, A = a) -- ou seja, o recall por grupo. Mede se
   o sistema acerta os casos positivos com a mesma competencia em todo grupo.
       EOD = max_a TPR_a - min_a TPR_a

Leitura das metricas: 0 e paridade perfeita. A literatura (Barocas, Hardt e
Narayanan, 2023) trata diferencas acima de 0,10 como materialmente relevantes.
Os dois criterios sao matematicamente incompativeis quando a prevalencia real
difere entre grupos -- e o caso aqui, e o RIA discute a escolha.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LIMIAR_ALERTA = 0.10


def metricas_por_grupo(dados: pd.DataFrame, coluna_grupo: str,
                       col_real: str = "y_real", col_pred: str = "y_pred") -> pd.DataFrame:
    """Calcula, por grupo protegido, a taxa de selecao e as taxas de acerto/erro."""
    linhas = []
    for grupo, bloco in dados.groupby(coluna_grupo):
        real = bloco[col_real].to_numpy()
        pred = bloco[col_pred].to_numpy()

        positivos = real == 1
        negativos = real == 0

        linhas.append({
            "grupo": grupo,
            "n": len(bloco),
            "prevalencia_real": round(float(real.mean()), 4),
            "taxa_selecao": round(float(pred.mean()), 4),
            "tpr_recall": round(float(pred[positivos].mean()) if positivos.any() else np.nan, 4),
            "fpr": round(float(pred[negativos].mean()) if negativos.any() else np.nan, 4),
            "precisao": round(float(real[pred == 1].mean()) if (pred == 1).any() else np.nan, 4),
        })

    return pd.DataFrame(linhas).sort_values("grupo").reset_index(drop=True)


def paridade_demografica(por_grupo: pd.DataFrame) -> dict:
    """Diferenca e razao das taxas de selecao entre grupos."""
    taxas = por_grupo["taxa_selecao"]
    maximo, minimo = float(taxas.max()), float(taxas.min())

    return {
        "metrica": "Paridade Demografica",
        "diferenca": round(maximo - minimo, 4),
        "razao": round(minimo / maximo, 4) if maximo > 0 else float("nan"),
        "grupo_mais_selecionado": por_grupo.loc[taxas.idxmax(), "grupo"],
        "grupo_menos_selecionado": por_grupo.loc[taxas.idxmin(), "grupo"],
        "aprovado": bool((maximo - minimo) <= LIMIAR_ALERTA),
    }


def igualdade_oportunidade(por_grupo: pd.DataFrame) -> dict:
    """Diferenca de recall (TPR) entre grupos."""
    tpr = por_grupo["tpr_recall"].dropna()
    maximo, minimo = float(tpr.max()), float(tpr.min())

    return {
        "metrica": "Igualdade de Oportunidade",
        "diferenca": round(maximo - minimo, 4),
        "razao": round(minimo / maximo, 4) if maximo > 0 else float("nan"),
        "grupo_melhor_atendido": por_grupo.loc[tpr.idxmax(), "grupo"],
        "grupo_pior_atendido": por_grupo.loc[tpr.idxmin(), "grupo"],
        "aprovado": bool((maximo - minimo) <= LIMIAR_ALERTA),
    }


def auditar(dados: pd.DataFrame, coluna_grupo: str = "faixa_renda_setor",
            titulo: str = "") -> dict:
    """Roda a auditoria completa e imprime o laudo."""
    por_grupo = metricas_por_grupo(dados, coluna_grupo)
    dp = paridade_demografica(por_grupo)
    eo = igualdade_oportunidade(por_grupo)

    print(f"\n=== Auditoria de fairness {titulo} ===")
    print(f"Grupo protegido: {coluna_grupo}\n")
    print(por_grupo.to_string(index=False))

    for teste in (dp, eo):
        status = "OK" if teste["aprovado"] else "ALERTA"
        print(f"\n[{status}] {teste['metrica']}: diferenca = {teste['diferenca']:.4f} "
              f"(limiar {LIMIAR_ALERTA:.2f}), razao = {teste['razao']:.4f}")

    if not dp["aprovado"]:
        print(f"  -> '{dp['grupo_mais_selecionado']}' e selecionado com muito mais "
              f"frequencia que '{dp['grupo_menos_selecionado']}'.")
    if not eo["aprovado"]:
        print(f"  -> o modelo acerta menos os positivos de "
              f"'{eo['grupo_pior_atendido']}' que os de '{eo['grupo_melhor_atendido']}'.")

    return {"por_grupo": por_grupo.to_dict("records"),
            "paridade_demografica": dp,
            "igualdade_oportunidade": eo}


def simular_mitigacao(dados: pd.DataFrame, coluna_grupo: str = "faixa_renda_setor",
                      col_prob: str = "y_prob", col_real: str = "y_real") -> pd.DataFrame:
    """Mitigacao por limiar especifico de grupo (post-processing de Hardt et al.).

    Em vez de um corte unico em 0,5, calibra o limiar de cada grupo para igualar
    a taxa de selecao. E a tecnica menos invasiva: nao exige retreinar o modelo
    nem alterar os dados, apenas ajustar a regra de decisao -- e e auditavel,
    porque o limiar de cada grupo fica explicito e documentado.
    """
    alvo = float((dados[col_prob] >= 0.5).mean())

    linhas = []
    for grupo, bloco in dados.groupby(coluna_grupo):
        limiar = float(np.quantile(bloco[col_prob], 1 - alvo))
        pred = (bloco[col_prob] >= limiar).astype(int)
        real = bloco[col_real].to_numpy()
        positivos = real == 1

        linhas.append({
            "grupo": grupo,
            "limiar_calibrado": round(limiar, 4),
            "taxa_selecao_antes": round(float((bloco[col_prob] >= 0.5).mean()), 4),
            "taxa_selecao_depois": round(float(pred.mean()), 4),
            "recall_depois": round(float(pred[positivos].mean()) if positivos.any() else np.nan, 4),
        })

    resultado = pd.DataFrame(linhas).sort_values("grupo").reset_index(drop=True)

    antes = resultado["taxa_selecao_antes"]
    depois = resultado["taxa_selecao_depois"]
    print("\n=== Simulacao de mitigacao (limiar por grupo) ===")
    print(resultado.to_string(index=False))
    print(f"\nDisparidade na taxa de selecao: {antes.max() - antes.min():.4f} -> "
          f"{depois.max() - depois.min():.4f}")

    return resultado


if __name__ == "__main__":
    import config
    teste = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")
    auditar(teste, titulo="- modelo de recuperabilidade")
    simular_mitigacao(teste)
