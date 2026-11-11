#!/usr/bin/env python3
"""Gera docs/AULA_SPRINT4_E3.md a partir do modelo, executando a trilha.

    python docs/gerar_aula.py

O material de aula cita dezenas de numeros (placares, metricas, contagens). Na
primeira versao eles foram digitados a mao, a partir de um script escrito a
parte -- e ficaram em desacordo com o codigo publicado, que nem sequer
executava em sequencia.

Aqui a relacao e invertida. O arquivo AULA_SPRINT4_E3.modelo.md traz o texto
com marcadores no lugar dos numeros. Este script:

  1. extrai os blocos python do modelo, na ordem;
  2. executa todos num projeto temporario (nada e gravado em data/ ou models/);
  3. calcula cada marcador a partir do que a execucao produziu;
  4. escreve o arquivo final.

Se um bloco nao executa, a aula nao e gerada. Se uma afirmacao do texto deixa
de ser verdadeira ("a regressao logistica vence"), o script falha e avisa.

Edite sempre o .modelo.md, nunca o arquivo final. tests/test_aula.py reexecuta
a trilha do arquivo final e confere que os dois continuam com o mesmo codigo.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import tempfile
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "docs" / "AULA_SPRINT4_E3.modelo.md"
FINAL = RAIZ / "docs" / "AULA_SPRINT4_E3.md"
CARTEIRA = RAIZ / "data" / "carteira_contribuintes.csv"

# Blocos que comecam assim sao contraexemplos: aparecem no texto, nao executam.
MARCAS_DE_CONTRAEXEMPLO = ("# ERRADO", "# ARMADILHA")

PADRAO_BLOCO = re.compile(r"^```python\n(.*?)^```", re.S | re.M)
PADRAO_MARCADOR = re.compile(r"⟦(\w+)⟧")


def extrair_blocos(texto: str) -> list[tuple[int, str]]:
    """Devolve (linha, codigo) de cada bloco python, na ordem do documento."""
    return [(texto[:m.start()].count("\n") + 1, m.group(1))
            for m in PADRAO_BLOCO.finditer(texto)]


def e_contraexemplo(codigo: str) -> bool:
    return codigo.lstrip().startswith(MARCAS_DE_CONTRAEXEMPLO)


def executar_trilha(texto: str, carteira: Path = CARTEIRA) -> tuple[dict, Path]:
    """Executa os blocos da aula, em ordem, num projeto temporario.

    Reproduz a estrutura que a aula pressupoe (notebooks/, data/, models/) e
    roda a partir de notebooks/, como o aluno faria. Devolve o namespace final
    e a raiz temporaria -- quem chama e responsavel por apaga-la.
    """
    raiz_tmp = Path(tempfile.mkdtemp(prefix="aula_sprint4_"))
    (raiz_tmp / "data").mkdir()
    (raiz_tmp / "notebooks").mkdir()
    shutil.copy2(carteira, raiz_tmp / "data" / carteira.name)

    namespace: dict = {}
    anterior = Path.cwd()
    os.chdir(raiz_tmp / "notebooks")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for linha, codigo in extrair_blocos(texto):
                if e_contraexemplo(codigo):
                    continue
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        exec(compile(codigo, f"<aula:linha {linha}>", "exec"), namespace)
                except Exception as erro:
                    raise RuntimeError(
                        f"o bloco da linha {linha} nao executa: "
                        f"{erro.__class__.__name__}: {erro}") from erro
    finally:
        os.chdir(anterior)

    return namespace, raiz_tmp


# --------------------------------------------------------------------------
# Formatacao em portugues
# --------------------------------------------------------------------------
def dec(valor: float, casas: int = 4) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def pct(valor: float, casas: int = 1) -> str:
    return f"{100 * valor:.{casas}f}%".replace(".", ",")


def milhar(valor: float) -> str:
    return f"{int(round(valor)):,}".replace(",", ".")


def tabela_md(cabecalho: list[str], linhas: list[list[str]]) -> str:
    partes = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    partes += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return "\n".join(partes)


def tabela_placar(placar, com_f1: bool) -> str:
    cabecalho = ["Modelo", "ROC-AUC na validação"] + (["F1 na validação"] if com_f1 else [])
    linhas = []
    for _, r in placar.iterrows():
        linha = [r["modelo"], dec(r["roc_auc"])]
        if com_f1:
            linha.append(dec(r["f1"]))
        linhas.append(linha)
    return tabela_md(cabecalho, linhas)


# --------------------------------------------------------------------------
# Calculo dos marcadores
# --------------------------------------------------------------------------
def calcular_marcadores(ns: dict, raiz_tmp: Path) -> dict[str, str]:
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    m: dict[str, str] = {}
    dados, universo = ns["dados"], ns["universo"]
    treino, teste = ns["treino"], ns["teste"]

    # ---- Secao 2
    m["n_total"] = milhar(len(dados))
    m["n_excl"] = milhar(len(dados) - len(universo))
    m["n_universo"] = milhar(len(universo))
    m["prev_inad"] = pct(universo["inadimplente_proximo_exercicio"].mean())
    m["n_com_divida"] = milhar((universo["valor_divida_consolidada"] > 0).sum())

    # ---- Secao 3.2: a armadilha, medida no mesmo universo
    cd = universo[universo["valor_divida_consolidada"] > 0]
    data_derivada = pd.Timestamp("2026-11-11") - pd.to_timedelta(
        cd["tempo_inadimplencia_dias"], unit="D")
    antigo = data_derivada <= data_derivada.quantile(0.80)
    m["trap_tr_dias"] = milhar(cd.loc[antigo, "tempo_inadimplencia_dias"].mean())
    m["trap_te_dias"] = milhar(cd.loc[~antigo, "tempo_inadimplencia_dias"].mean())
    m["trap_tr_rec"] = pct(cd.loc[antigo, "divida_recuperada_12m"].mean())
    m["trap_te_rec"] = pct(cd.loc[~antigo, "divida_recuperada_12m"].mean())
    assert (cd.loc[~antigo, "divida_recuperada_12m"].mean()
            - cd.loc[antigo, "divida_recuperada_12m"].mean()) > 0.10, \
        "a armadilha da secao 3.2 deixou de produzir distribuicoes incomparaveis"

    # ---- Secao 3.3: split temporal x aleatorio (mesmo modelo, mesmos atributos)
    # Um unico sorteio nao basta para comparar: a metrica de teste oscila.
    atributos, alvo, semente = ns["ATRIBUTOS"], ns["ALVO"], ns["SEMENTE"]
    aucs_aleatorios = []
    for sorteio in range(20):
        X_a, X_b, y_a, y_b = train_test_split(
            universo[atributos], universo[alvo], test_size=len(teste) / len(universo),
            random_state=sorteio, stratify=universo[alvo])
        aleatorio = ns["montar_modelo"](
            LogisticRegression(max_iter=1000, random_state=semente)).fit(X_a, y_a)
        aucs_aleatorios.append(roc_auc_score(y_b, aleatorio.predict_proba(X_b)[:, 1]))
    auc_temporal = ns["metricas_inadimplencia"]["roc_auc"]
    assert min(aucs_aleatorios) <= auc_temporal <= max(aucs_aleatorios),         "o split temporal saiu da faixa dos aleatorios: reveja a nota da secao 3.3"
    m["auc_temporal"] = dec(auc_temporal, 3)
    m["auc_rand_min"] = dec(min(aucs_aleatorios), 3)
    m["auc_rand_max"] = dec(max(aucs_aleatorios), 3)

    # ---- Secao 3.4 e 3.5
    m["n_treino"], m["n_teste"] = milhar(len(treino)), milhar(len(teste))
    m["pct_treino"] = pct(len(treino) / len(universo), 0)
    m["pct_teste"] = pct(len(teste) / len(universo), 0)
    cs = ns["comparacao_split"]
    m["tabela_split"] = tabela_md(
        ["Média", "Treino", "Teste"],
        [["Valor venal (R$)", milhar(cs.loc["valor_venal", "treino"]),
          milhar(cs.loc["valor_venal", "teste"])],
         ["Exercícios inadimplentes (5 anos)",
          dec(cs.loc["exercicios_inadimplentes_5a", "treino"], 2),
          dec(cs.loc["exercicios_inadimplentes_5a", "teste"], 2)],
         ["Taxa de inadimplência",
          pct(cs.loc["inadimplente_proximo_exercicio", "treino"]),
          pct(cs.loc["inadimplente_proximo_exercicio", "teste"])]])

    # ---- Secao 5
    placar = ns["placar"]
    m["tabela_placar_baselines"] = tabela_placar(placar, com_f1=True)
    assert placar.loc[placar["f1"].idxmax(), "modelo"].startswith("trivial"), \
        "o trivial deixou de ter o melhor F1: reescreva a secao 5"

    prob_val, y_val, limiar = ns["prob_val"], ns["y_val"], ns["LIMIAR"]
    linhas = []
    for corte in (0.35, 0.40, 0.45, 0.50, 0.55):
        previsto = prob_val >= corte
        linhas.append([dec(corte, 2), dec(f1_score(y_val, previsto)),
                       dec(precision_score(y_val, previsto), 3),
                       dec(recall_score(y_val, previsto), 3)])
    m["tabela_limiares"] = tabela_md(["Limiar", "F1", "Precisão", "Recall"], linhas)

    p = float(np.mean(y_val))
    f1_trivial = 2 * p / (p + 1)
    f1_no_limiar = f1_score(y_val, prob_val >= limiar)
    assert f1_no_limiar > f1_trivial, "no melhor limiar o modelo nao supera o trivial"
    m["lim_melhor"], m["LIMIAR"] = dec(limiar, 2), dec(limiar, 2)
    m["f1_melhor"] = dec(f1_no_limiar)
    m["f1_trivial_val"] = dec(f1_trivial)

    # ---- Secao 6
    pf = ns["placar_final"].reset_index(drop=True)
    m["tabela_placar_final"] = tabela_placar(pf, com_f1=False)
    assert pf.loc[0, "modelo"] == "regressão logística", \
        "a regressao logistica deixou de vencer o Modelo 1: reescreva a secao 6"
    log_auc = float(pf.loc[pf["modelo"] == "regressão logística", "roc_auc"].iloc[0])
    rf_auc = float(ns["busca"].best_score_)
    m["log_auc"], m["rf_auc"] = dec(log_auc, 3), dec(rf_auc, 3)
    m["dif_auc"] = dec(log_auc - rf_auc, 3)

    # ---- Secao 7: a troca do limiar, medida na validacao
    assert limiar < 0.5, "o limiar escolhido nao favorece recall: reescreva a secao 7"
    em50, emlim = prob_val >= 0.5, prob_val >= limiar
    vp50, vplim = int((em50 & (y_val == 1)).sum()), int((emlim & (y_val == 1)).sum())
    fp50, fplim = int((em50 & (y_val == 0)).sum()), int((emlim & (y_val == 0)).sum())
    rec50, reclim = recall_score(y_val, em50), recall_score(y_val, emlim)
    m["rec_val_50"], m["rec_val_lim"] = dec(rec50, 3), dec(reclim, 3)
    m["dif_rec"] = dec(reclim - rec50, 2)
    m["vp_val_50"], m["vp_val_lim"] = milhar(vp50), milhar(vplim)
    m["fp_val_50"], m["fp_val_lim"] = milhar(fp50), milhar(fplim)
    m["ganho_vp"], m["custo_fp"] = milhar(vplim - vp50), milhar(fplim - fp50)

    mi = ns["metricas_inadimplencia"]
    (_, fp), (fn, _) = mi["matriz_confusao"]
    m["t_acc"], m["t_prec"] = dec(mi["acuracia"], 3), dec(mi["precisao"], 3)
    m["t_rec"], m["t_f1"], m["t_auc"] = dec(mi["recall"], 3), dec(mi["f1"], 3), dec(mi["roc_auc"], 3)
    m["t_matriz"] = str(mi["matriz_confusao"])
    m["t_fn"], m["t_fp"] = milhar(fn), milhar(fp)

    pr = ns["por_renda"].set_index("grupo")
    m["tabela_subgrupo"] = tabela_md(
        ["Faixa de renda do setor", "n", "Prevalência real", "Taxa de seleção", "Recall", "Precisão"],
        [[g, milhar(pr.loc[g, "n"]), pct(pr.loc[g, "prevalencia"]), pct(pr.loc[g, "taxa_selecao"]),
          dec(pr.loc[g, "recall"], 3), dec(pr.loc[g, "precisao"], 3)] for g in ("alta", "media", "baixa")])
    assert pr.loc["baixa", "taxa_selecao"] - pr.loc["alta", "taxa_selecao"] > 0.10, \
        "a disparidade por renda deixou de aparecer: reescreva o fim da secao 7"
    m["sel_baixa"], m["sel_alta"] = pct(pr.loc["baixa", "taxa_selecao"], 0), pct(pr.loc["alta", "taxa_selecao"], 0)

    # ---- Secao 8
    prf = ns["placar_rec_final"].reset_index(drop=True)
    m["tabela_placar_rec"] = tabela_placar(prf, com_f1=False)
    assert prf.loc[0, "modelo"] == "regressão logística", \
        "a regressao logistica deixou de vencer o Modelo 2: reescreva a secao 8"
    m["rec_auc_teste"] = dec(ns["metricas_recuperabilidade"]["roc_auc"], 3)

    cal = ns["calibracao"]
    assert cal["casos"].notna().all() and (cal["casos"] > 0).all(), "ha faixa vazia na calibracao"
    assert cal.loc["alta", "taxa_observada"] > cal.loc["media", "taxa_observada"] \
        > cal.loc["baixa", "taxa_observada"], "as faixas nao estao em ordem: reescreva a secao 8"
    m["tabela_calibracao"] = tabela_md(
        ["Faixa", "Casos", "Probabilidade média prevista", "Taxa de recuperação observada"],
        [[f, milhar(cal.loc[f, "casos"]), pct(cal.loc[f, "prob_media_prevista"]),
          pct(cal.loc[f, "taxa_observada"])] for f in ("alta", "media", "baixa")])
    m["cal_alta_prev"], m["cal_alta_obs"] = pct(cal.loc["alta", "prob_media_prevista"], 0), pct(cal.loc["alta", "taxa_observada"], 0)
    m["cal_baixa_prev"], m["cal_baixa_obs"] = pct(cal.loc["baixa", "prob_media_prevista"], 0), pct(cal.loc["baixa", "taxa_observada"], 0)
    m["pct_media"] = pct(cal.loc["media", "casos"] / cal["casos"].sum(), 0)

    # ---- Secao 9
    tamanho = sum(a.stat().st_size for a in (raiz_tmp / "models").glob("modelo_*.joblib"))
    m["tam_modelos"] = f"{tamanho / 1024:.0f} KB"

    return m


def main() -> int:
    modelo = MODELO.read_text(encoding="utf-8")
    print("Executando a trilha da aula...")
    namespace, raiz_tmp = executar_trilha(modelo)
    try:
        marcadores = calcular_marcadores(namespace, raiz_tmp)
    finally:
        shutil.rmtree(raiz_tmp, ignore_errors=True)

    usados = set(PADRAO_MARCADOR.findall(modelo))
    faltando = usados - set(marcadores)
    if faltando:
        raise SystemExit(f"marcadores sem valor: {sorted(faltando)}")

    final = PADRAO_MARCADOR.sub(lambda c: marcadores[c.group(1)], modelo)
    FINAL.write_text(final, encoding="utf-8", newline="\n")

    blocos = extrair_blocos(modelo)
    executados = sum(1 for _, c in blocos if not e_contraexemplo(c))
    print(f"  {executados} blocos executados, {len(blocos) - executados} contraexemplos")
    print(f"  {len(usados)} marcadores preenchidos")
    print(f"  {FINAL.relative_to(RAIZ)} gerado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
