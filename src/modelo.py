"""Treino e avaliacao dos dois modelos do sistema (Sprint 3 - Modulo 6).

Modelo 1 - Classificacao de inadimplencia
    Prediz se o contribuinte ficara inadimplente no proximo exercicio.

Modelo 2 - Scoring de recuperabilidade
    Entre os que ja possuem divida inscrita, estima a probabilidade de
    recuperacao em 12 meses. E o modelo que ordena a fila de cobranca.

DECISAO DE PROJETO: a faixa de renda do setor NAO entra como atributo preditivo.
Ela e usada apenas como grupo protegido na auditoria de fairness. Excluir o
atributo nao elimina o vies (outras variaveis sao correlacionadas com renda),
mas evita que o modelo discrimine por renda de forma direta e explicita.
"""

from __future__ import annotations

import json

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

import config

# Grupo protegido: usado so na auditoria, nunca como preditor.
COLUNA_PROTEGIDA = "faixa_renda_setor"

ATRIBUTOS_NUMERICOS = [
    "area_construida_m2", "valor_venal", "valor_iptu_anual", "distancia_centro_km",
    "exercicios_inadimplentes_5a", "tempo_inadimplencia_dias",
    "valor_divida_consolidada", "qtd_parcelamentos_anteriores",
    "parcelamento_rompido", "qtd_notificacoes",
]
ATRIBUTOS_CATEGORICOS = ["tipo_imovel", "setor_urbano"]


def _montar_pipeline() -> Pipeline:
    preparo = ColumnTransformer([
        ("categoricos", OneHotEncoder(handle_unknown="ignore"), ATRIBUTOS_CATEGORICOS),
        ("numericos", "passthrough", ATRIBUTOS_NUMERICOS),
    ])
    return Pipeline([
        ("preparo", preparo),
        ("classificador", HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.08, max_depth=6,
            random_state=config.SEMENTE)),
    ])


def _avaliar(nome: str, y_real, y_previsto, y_prob) -> dict:
    matriz = confusion_matrix(y_real, y_previsto)
    metricas = {
        "acuracia": round(float(accuracy_score(y_real, y_previsto)), 4),
        "precisao": round(float(precision_score(y_real, y_previsto, zero_division=0)), 4),
        "recall": round(float(recall_score(y_real, y_previsto, zero_division=0)), 4),
        "f1": round(float(f1_score(y_real, y_previsto, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_real, y_prob)), 4),
        "average_precision": round(float(average_precision_score(y_real, y_prob)), 4),
        "matriz_confusao": matriz.tolist(),
        "n_teste": int(len(y_real)),
    }

    print(f"\n--- {nome} ---")
    print(f"  acuracia {metricas['acuracia']:.3f} | precisao {metricas['precisao']:.3f} | "
          f"recall {metricas['recall']:.3f} | F1 {metricas['f1']:.3f} | "
          f"ROC-AUC {metricas['roc_auc']:.3f}")
    print(f"  matriz de confusao [[VN, FP], [FN, VP]] = {matriz.tolist()}")
    print(classification_report(y_real, y_previsto, zero_division=0,
                                target_names=["negativo", "positivo"]))
    return metricas


def _excluir_grupo_protegido(dados: pd.DataFrame) -> pd.DataFrame:
    """Remove beneficiarios do IPTU Social das acoes preditivas de cobranca.

    Exigencia da secao 11 do plano de ensino: idosos, aposentados, pensionistas
    e PCD de baixa renda sao isentos e nao podem ser alvo do modelo.
    """
    antes = len(dados)
    filtrado = dados[dados["iptu_social"] == 0].copy()
    print(f"  IPTU Social: {antes - len(filtrado)} contribuintes isentos excluidos "
          f"do universo de cobranca ({antes} -> {len(filtrado)})")
    return filtrado


def treinar(dados: pd.DataFrame) -> dict:
    """Treina os dois modelos e devolve o dicionario de metricas."""
    dados = _excluir_grupo_protegido(dados)
    resultado: dict = {}

    # ---------------- Modelo 1: inadimplencia ----------------
    print("\n[1/2] Treinando classificador de inadimplencia...")
    X = dados[ATRIBUTOS_CATEGORICOS + ATRIBUTOS_NUMERICOS]
    y = dados["inadimplente_proximo_exercicio"]

    X_tr, X_te, y_tr, y_te, prot_tr, prot_te = train_test_split(
        X, y, dados[COLUNA_PROTEGIDA], test_size=0.25,
        random_state=config.SEMENTE, stratify=y)

    modelo_inad = _montar_pipeline()
    modelo_inad.fit(X_tr, y_tr)

    prob = modelo_inad.predict_proba(X_te)[:, 1]
    pred = (prob >= 0.5).astype(int)
    resultado["inadimplencia"] = _avaliar("Modelo 1: inadimplencia", y_te, pred, prob)

    joblib.dump(modelo_inad, config.MODELO_INADIMPLENCIA)

    # Guarda o conjunto de teste para a auditoria de fairness.
    teste_inad = X_te.copy()
    teste_inad["y_real"] = y_te.to_numpy()
    teste_inad["y_prob"] = prob
    teste_inad["y_pred"] = pred
    teste_inad[COLUNA_PROTEGIDA] = prot_te.to_numpy()
    teste_inad.to_csv(config.DADOS / "teste_inadimplencia.csv", sep=";", index=False)

    # ---------------- Modelo 2: recuperabilidade ----------------
    print("\n[2/2] Treinando modelo de scoring de recuperabilidade...")
    com_divida = dados[dados["valor_divida_consolidada"] > 0]
    print(f"  universo: {len(com_divida)} contribuintes com divida inscrita")

    Xr = com_divida[ATRIBUTOS_CATEGORICOS + ATRIBUTOS_NUMERICOS]
    yr = com_divida["divida_recuperada_12m"]

    Xr_tr, Xr_te, yr_tr, yr_te, protr_tr, protr_te = train_test_split(
        Xr, yr, com_divida[COLUNA_PROTEGIDA], test_size=0.25,
        random_state=config.SEMENTE, stratify=yr)

    modelo_rec = _montar_pipeline()
    modelo_rec.fit(Xr_tr, yr_tr)

    prob_r = modelo_rec.predict_proba(Xr_te)[:, 1]
    pred_r = (prob_r >= 0.5).astype(int)
    resultado["recuperabilidade"] = _avaliar("Modelo 2: recuperabilidade", yr_te, pred_r, prob_r)

    joblib.dump(modelo_rec, config.MODELO_RECUPERABILIDADE)

    teste_rec = Xr_te.copy()
    teste_rec["y_real"] = yr_te.to_numpy()
    teste_rec["y_prob"] = prob_r
    teste_rec["y_pred"] = pred_r
    teste_rec[COLUNA_PROTEGIDA] = protr_te.to_numpy()
    teste_rec.to_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";", index=False)

    with open(config.METRICAS, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    return resultado


def faixa_recuperabilidade(probabilidade: float) -> str:
    """Traduz o score continuo nas faixas exigidas pelo plano de ensino."""
    if probabilidade >= 0.66:
        return "alta"
    if probabilidade >= 0.33:
        return "media"
    return "baixa"


def priorizar_cobranca(dados: pd.DataFrame) -> pd.DataFrame:
    """Gera a fila de cobranca ordenada por retorno esperado.

    retorno_esperado = valor_divida * P(recuperacao)

    Ordenar pela probabilidade pura privilegiaria dividas pequenas e faceis;
    ordenar pelo valor puro privilegiaria dividas grandes e incobraveis. O
    produto equilibra os dois -- e a metrica que a Sefin usaria na pratica.
    """
    modelo = joblib.load(config.MODELO_RECUPERABILIDADE)

    universo = dados[(dados["valor_divida_consolidada"] > 0) & (dados["iptu_social"] == 0)].copy()
    X = universo[ATRIBUTOS_CATEGORICOS + ATRIBUTOS_NUMERICOS]

    universo["prob_recuperacao"] = modelo.predict_proba(X)[:, 1]
    universo["faixa_recuperabilidade"] = universo["prob_recuperacao"].map(faixa_recuperabilidade)
    universo["retorno_esperado"] = (universo["valor_divida_consolidada"]
                                    * universo["prob_recuperacao"]).round(2)

    return universo.sort_values("retorno_esperado", ascending=False).reset_index(drop=True)


def importancia_atributos(dados: pd.DataFrame, qual: str = "recuperabilidade",
                          n_amostra: int = 3000) -> pd.DataFrame:
    """Importancia por permutacao -- base do direito a explicacao (LGPD Art. 20)."""
    from sklearn.inspection import permutation_importance

    caminho = (config.MODELO_RECUPERABILIDADE if qual == "recuperabilidade"
               else config.MODELO_INADIMPLENCIA)
    modelo = joblib.load(caminho)

    base = dados[dados["valor_divida_consolidada"] > 0] if qual == "recuperabilidade" else dados
    alvo = "divida_recuperada_12m" if qual == "recuperabilidade" else "inadimplente_proximo_exercicio"

    amostra = base.sample(min(n_amostra, len(base)), random_state=config.SEMENTE)
    X = amostra[ATRIBUTOS_CATEGORICOS + ATRIBUTOS_NUMERICOS]
    y = amostra[alvo]

    resultado = permutation_importance(modelo, X, y, n_repeats=5,
                                       random_state=config.SEMENTE, scoring="roc_auc")

    return (pd.DataFrame({"atributo": X.columns,
                          "importancia": resultado.importances_mean.round(4)})
            .sort_values("importancia", ascending=False)
            .reset_index(drop=True))


if __name__ == "__main__":
    import etl
    treinar(etl.carregar_visao_analitica())
