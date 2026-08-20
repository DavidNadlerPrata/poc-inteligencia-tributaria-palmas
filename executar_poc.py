#!/usr/bin/env python3
"""Orquestrador do PoC: roda o pipeline completo de ponta a ponta.

    python executar_poc.py            # usa cache quando existir
    python executar_poc.py --coletar  # forca nova coleta na API da Prefeitura

Percorre, na ordem, as cinco sprints do Projeto Integrador:
    Sprint 1  esquema relacional e carga
    Sprint 2  coleta via API REST + ETL
    Sprint 3  treino dos modelos e fila de cobranca
    Sprint 4  auditoria de fairness e mitigacao
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import config
from src import coleta, etl, fairness, modelo, sintetico


def cabecalho(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC - Inteligencia Tributaria Palmas-TO")
    parser.add_argument("--coletar", action="store_true",
                        help="forca nova coleta na API (ignora o cache local)")
    parser.add_argument("--ano", default="2025", help="ano da arrecadacao a coletar")
    parser.add_argument("--sem-rede", action="store_true",
                        help="pula a coleta online e usa apenas dados locais")
    args = parser.parse_args()

    cabecalho("PoC - Inteligencia Tributaria: Predicao de Inadimplencia e "
              "Priorizacao da Divida Ativa de Palmas-TO")

    # ---------------- Sprint 2: coleta real ----------------
    cabecalho("[Sprint 2] Coleta de dados reais via API REST da Prefeitura de Palmas")
    arrecadacao = None
    if args.sem_rede:
        print("Modo --sem-rede: coleta online ignorada.")
    else:
        try:
            arrecadacao = coleta.coletar(ano=args.ano, forcar=args.coletar)
            print(f"  arrecadacao real: {len(arrecadacao)} registros de {args.ano}")
        except Exception as erro:  # rede instavel nao pode derrubar o PoC inteiro
            print(f"  ! coleta indisponivel ({erro.__class__.__name__}: {erro})")
            print("  o pipeline segue com a carteira local; rode de novo com --coletar depois.")

    # ---------------- Carteira de contribuintes ----------------
    cabecalho("[Base analitica] Carteira de contribuintes (sintetica, calibrada)")
    print("Dados individuais de divida ativa nao sao publicos (LGPD).")
    print("A carteira e sintetica, calibrada pelos agregados oficiais da Sefin.")
    print("Ver docs/RIA.md, secao 1, e o cabecalho de src/sintetico.py.\n")
    carteira = sintetico.gerar(forcar=args.coletar)

    # ---------------- Sprint 1 e 2: ETL e banco ----------------
    cabecalho("[Sprint 1+2] Pipeline ETL e carga no banco relacional")
    etl.executar(carteira, arrecadacao)
    dados = etl.carregar_visao_analitica()
    print(f"  visao analitica: {len(dados)} contribuintes, {dados.shape[1]} colunas")

    # ---------------- Sprint 3: modelos ----------------
    # treinar() ja imprime as metricas e grava models/metricas.json.
    cabecalho("[Sprint 3] Treino e avaliacao dos modelos de Machine Learning")
    modelo.treinar(dados)

    cabecalho("[Sprint 3] Fila de cobranca priorizada por retorno esperado")
    fila = modelo.priorizar_cobranca(dados)
    total_divida = fila["valor_divida_consolidada"].sum()
    retorno_total = fila["retorno_esperado"].sum()

    print(f"  contribuintes com divida inscrita: {len(fila)}")
    print(f"  divida ativa na carteira:  R$ {total_divida:,.2f}")
    print(f"  retorno esperado total:    R$ {retorno_total:,.2f} "
          f"({retorno_total / total_divida:.1%} da carteira)")

    top = max(1, int(len(fila) * 0.20))
    captura = fila.head(top)["retorno_esperado"].sum() / retorno_total
    print(f"  concentracao: os 20% melhores casos concentram {captura:.1%} do retorno esperado")

    print("\n  Top 10 da fila de cobranca:")
    colunas = ["setor_urbano", "valor_divida_consolidada", "prob_recuperacao",
               "faixa_recuperabilidade", "retorno_esperado"]
    print(fila.head(10)[colunas].to_string(index=False))

    fila.to_csv(config.DADOS / "fila_cobranca.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---------------- Sprint 3: explicabilidade ----------------
    cabecalho("[Sprint 3] Interpretabilidade - direito a explicacao (LGPD Art. 20)")
    importancia = modelo.importancia_atributos(dados, "recuperabilidade")
    print(importancia.head(10).to_string(index=False))
    importancia.to_csv(config.DADOS / "importancia_atributos.csv", sep=";", index=False)

    # ---------------- Sprint 4: fairness ----------------
    cabecalho("[Sprint 4] Auditoria de justica algoritmica")
    import pandas as pd
    teste_inad = pd.read_csv(config.DADOS / "teste_inadimplencia.csv", sep=";")
    teste_rec = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")

    auditoria = {
        "inadimplencia": fairness.auditar(teste_inad, titulo="- Modelo 1 (inadimplencia)"),
        "recuperabilidade": fairness.auditar(teste_rec, titulo="- Modelo 2 (recuperabilidade)"),
    }
    mitigacao = fairness.simular_mitigacao(teste_rec)

    for chave in auditoria:
        auditoria[chave]["por_grupo"] = auditoria[chave]["por_grupo"]
    with open(config.DADOS / "auditoria_fairness.json", "w", encoding="utf-8") as arquivo:
        json.dump(auditoria, arquivo, ensure_ascii=False, indent=2, default=str)
    mitigacao.to_csv(config.DADOS / "mitigacao_fairness.csv", sep=";", index=False)

    # ---------------- Encerramento ----------------
    cabecalho("PoC concluido")
    print(f"  banco de dados ....... {config.BANCO}")
    print(f"  modelos serializados . {config.MODELOS}")
    print(f"  metricas ............. {config.METRICAS.name}")
    print("  fila de cobranca ..... fila_cobranca.csv")
    print("  auditoria fairness ... auditoria_fairness.json")
    print("\n  Painel interativo:  streamlit run app/painel.py")

    aprovados = all(auditoria[m][t]["aprovado"]
                    for m in auditoria
                    for t in ("paridade_demografica", "igualdade_oportunidade"))
    if not aprovados:
        print("\n  ATENCAO: a auditoria apontou disparidade acima do limiar.")
        print("  Discussao e plano de mitigacao em docs/RIA.md, secao 2.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
