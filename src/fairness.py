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

Leitura das metricas: 0 e paridade perfeita. O limite de disparidade de 0,10 para
a diferenca e a convencao do AI Fairness 360 (Bellamy et al., IBM, 2019), que
considera justa a diferenca de paridade entre -0,1 e 0,1. A referencia juridica
mais antiga e a regra dos quatro quintos da EEOC (1978): razao entre taxas de
selecao de ao menos 0,8 -- que Barocas, Hardt e Narayanan (2023) tratam como
referencia, nao como regra estrita. Por isso o laudo informa diferenca e razao.
Os dois criterios sao matematicamente incompativeis quando a prevalencia real
difere entre grupos -- e o caso aqui, e o RIA discute a escolha.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LIMITE_DISPARIDADE = 0.10


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
        "aprovado": bool((maximo - minimo) <= LIMITE_DISPARIDADE),
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
        "aprovado": bool((maximo - minimo) <= LIMITE_DISPARIDADE),
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
              f"(limite {LIMITE_DISPARIDADE:.2f}), razao = {teste['razao']:.4f}")

    if not dp["aprovado"]:
        print(f"  -> '{dp['grupo_mais_selecionado']}' e selecionado com muito mais "
              f"frequencia que '{dp['grupo_menos_selecionado']}'.")
    if not eo["aprovado"]:
        print(f"  -> o modelo acerta menos os positivos de "
              f"'{eo['grupo_pior_atendido']}' que os de '{eo['grupo_melhor_atendido']}'.")

    return {"por_grupo": por_grupo.to_dict("records"),
            "paridade_demografica": dp,
            "igualdade_oportunidade": eo}


def intervalo_bootstrap(dados: pd.DataFrame, coluna_grupo: str = "faixa_renda_setor",
                        col_real: str = "y_real", col_pred: str = "y_pred",
                        n_reamostras: int = 2000, nivel: float = 0.95,
                        semente: int = 42) -> dict:
    """Intervalo de confianca por bootstrap para as duas diferencas.

    Reamostra os registros com reposicao DENTRO de cada grupo -- o tamanho de
    cada grupo fica igual ao do teste -- e recalcula as diferencas de taxa de
    selecao e de recall. O intervalo e o dos percentis da distribuicao obtida.

    Mede a incerteza de amostragem do conjunto de teste: com poucos casos num
    grupo, uma diferenca de 0,12 pode ser ruido. NAO mede a variacao que viria
    de treinar o modelo de novo, nem muda o criterio de aprovacao, que continua
    sendo a estimativa pontual contra o limite fixado antes da auditoria.

    Cuidado de leitura: a diferenca e o maximo menos o minimo de tres taxas, e
    o ruido infla o maximo. O intervalo tende, portanto, a ficar um pouco
    deslocado para cima.
    """
    rng = np.random.default_rng(semente)
    selecao, recall = [], []
    for _, bloco in dados.groupby(coluna_grupo):
        real = bloco[col_real].to_numpy()
        pred = bloco[col_pred].to_numpy()
        indices = rng.integers(0, len(bloco), size=(n_reamostras, len(bloco)))
        real_r, pred_r = real[indices], pred[indices]
        selecao.append(pred_r.mean(axis=1))
        positivos = real_r == 1
        with np.errstate(invalid="ignore"):
            recall.append((pred_r * positivos).sum(axis=1) / positivos.sum(axis=1))

    cauda = (1 - nivel) / 2 * 100
    resultado = {"n_reamostras": n_reamostras, "nivel": nivel}
    pontuais = {"paridade_demografica": paridade_demografica,
                "igualdade_oportunidade": igualdade_oportunidade}
    por_grupo = metricas_por_grupo(dados, coluna_grupo, col_real, col_pred)
    for nome, taxas in (("paridade_demografica", selecao), ("igualdade_oportunidade", recall)):
        matriz = np.vstack(taxas)
        diferencas = np.nanmax(matriz, axis=0) - np.nanmin(matriz, axis=0)
        resultado[nome] = {
            "diferenca": pontuais[nome](por_grupo)["diferenca"],
            "ic_inferior": round(float(np.nanpercentile(diferencas, cauda)), 4),
            "ic_superior": round(float(np.nanpercentile(diferencas, 100 - cauda)), 4),
            "prob_acima_do_limite": round(float(np.nanmean(diferencas > LIMITE_DISPARIDADE)), 4),
        }
    return resultado


def simular_mitigacao(dados: pd.DataFrame, coluna_grupo: str = "faixa_renda_setor",
                      col_prob: str = "y_prob", col_real: str = "y_real") -> pd.DataFrame:
    """Mitigacao por corte especifico de grupo (post-processing de Hardt et al.).

    Em vez de um corte unico em 0,5, calibra o corte de cada grupo para igualar
    a taxa de selecao. E a tecnica menos invasiva: nao exige retreinar o modelo
    nem alterar os dados, apenas ajustar a regra de decisao -- e e auditavel,
    porque o corte de cada grupo fica explicito e documentado.
    """
    alvo = float((dados[col_prob] >= 0.5).mean())

    linhas = []
    for grupo, bloco in dados.groupby(coluna_grupo):
        corte = float(np.quantile(bloco[col_prob], 1 - alvo))
        pred = (bloco[col_prob] >= corte).astype(int)
        real = bloco[col_real].to_numpy()
        positivos = real == 1

        linhas.append({
            "grupo": grupo,
            "corte_calibrado": round(corte, 4),
            "taxa_selecao_antes": round(float((bloco[col_prob] >= 0.5).mean()), 4),
            "taxa_selecao_depois": round(float(pred.mean()), 4),
            "recall_depois": round(float(pred[positivos].mean()) if positivos.any() else np.nan, 4),
        })

    resultado = pd.DataFrame(linhas).sort_values("grupo").reset_index(drop=True)

    antes = resultado["taxa_selecao_antes"]
    depois = resultado["taxa_selecao_depois"]
    print("\n=== Simulacao de mitigacao (corte por grupo) ===")
    print(resultado.to_string(index=False))
    print(f"\nDisparidade na taxa de selecao: {antes.max() - antes.min():.4f} -> "
          f"{depois.max() - depois.min():.4f}")

    return resultado


if __name__ == "__main__":
    import config
    teste = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")
    auditar(teste, titulo="- modelo de recuperabilidade")
    simular_mitigacao(teste)
