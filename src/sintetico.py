"""Gerador da carteira de contribuintes usada no PoC.

POR QUE DADOS SINTETICOS?
-------------------------
A predicao de inadimplencia exige o registro individual do contribuinte
(inscricao imobiliaria, valor devido, historico de pagamento). Esse dado NAO e
publico: e protegido pela LGPD e so pode ser acessado mediante convenio formal
com a Sefin, com base legal e termo de tratamento de dados.

O que e publico -- e o que este PoC coleta de verdade em `coleta.py` -- sao os
AGREGADOS de arrecadacao (valor por codigo de receita, orgao e mes).

A solucao adotada aqui e a mesma de qualquer prova de conceito em dominio
sensivel: um gerador sintetico CALIBRADO pelos agregados reais. Os totais de
divida ativa, o numero de imoveis tributaveis e a meta de adimplencia vem dos
numeros oficiais da Sefin citados no plano de ensino. A estrutura de colunas
reproduz a de um cadastro imobiliario municipal, de modo que trocar este modulo
pela extracao real exige apenas reapontar a origem -- o restante do pipeline
(ETL, features, modelo, fairness, painel) permanece identico.

VIES DELIBERADO
---------------
O processo gerador embute uma correlacao entre renda do setor e inadimplencia,
que existe na realidade fiscal brasileira. Isso e proposital: sem um vies real,
a analise de fairness da Sprint 4 seria um exercicio vazio. O modelo vai
aprender essa correlacao, os testes de equidade vao detecta-la e o RIA discute
a mitigacao.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

import config


def _sortear_setores(rng: np.random.Generator, n: int) -> pd.DataFrame:
    nomes = [s[0] for s in config.SETORES_URBANOS]
    pesos = np.array([s[2] for s in config.SETORES_URBANOS], dtype=float)
    pesos = pesos / pesos.sum()

    escolhidos = rng.choice(len(nomes), size=n, p=pesos)
    return pd.DataFrame({
        "setor_urbano": [config.SETORES_URBANOS[i][0] for i in escolhidos],
        "faixa_renda_setor": [config.SETORES_URBANOS[i][1] for i in escolhidos],
        "_fator_valor": [config.SETORES_URBANOS[i][3] for i in escolhidos],
    })


def _pseudonimizar(indice: int) -> str:
    """Pseudonimiza a inscricao imobiliaria (LGPD, Art. 13).

    Em producao o sal viria de um cofre de segredos, nunca do codigo-fonte.
    """
    bruto = f"inscricao-imobiliaria-{indice:08d}".encode()
    return hashlib.sha256(bruto).hexdigest()[:16]


def gerar_carteira(n: int | None = None, semente: int | None = None) -> pd.DataFrame:
    """Gera a carteira de contribuintes de IPTU com historico e alvos."""
    n = n or config.TAMANHO_AMOSTRA
    rng = np.random.default_rng(semente or config.SEMENTE)

    setores = _sortear_setores(rng, n)
    fator = setores["_fator_valor"].to_numpy()
    renda = setores["faixa_renda_setor"].to_numpy()

    # ---------------- Atributos cadastrais do imovel ----------------
    tipo_imovel = rng.choice(config.TIPOS_IMOVEL, size=n, p=[0.72, 0.18, 0.07, 0.03])

    # Area construida: log-normal (cauda longa), zerada em terrenos.
    area = rng.lognormal(mean=4.75, sigma=0.55, size=n) * np.sqrt(fator)
    area = np.where(tipo_imovel == "terreno", 0.0, area.round(1))

    # Valor venal calibrado pelo fator do setor.
    valor_venal = (rng.lognormal(mean=12.0, sigma=0.6, size=n) * fator).round(2)

    # IPTU anual: aliquota efetiva ~0,6% do valor venal, com ruido.
    aliquota = rng.normal(0.006, 0.0012, size=n).clip(0.002, 0.012)
    valor_iptu = (valor_venal * aliquota).round(2)

    # Geometria analitica (Modulo 1): distancia euclidiana ao centro urbano.
    # Setores de renda alta ficam, em media, mais proximos do centro.
    base_dist = np.where(renda == "alta", 3.0, np.where(renda == "media", 7.0, 13.0))
    distancia_centro = np.abs(rng.normal(base_dist, 3.0)).round(2)

    # ---------------- Historico fiscal ----------------
    # Propensao latente a inadimplencia: renda do setor pesa, mas nao decide.
    peso_renda = np.where(renda == "baixa", 0.75, np.where(renda == "media", 0.20, -0.35))
    # Carga tributaria relativa: IPTU alto para o padrao do setor pressiona mais.
    carga_relativa = (valor_iptu / np.maximum(valor_venal * 0.006, 1.0) - 1.0).clip(-1, 2)
    propensao = (peso_renda + 0.45 * carga_relativa
                 + 0.30 * (tipo_imovel == "terreno")
                 + 0.015 * distancia_centro
                 + rng.normal(0, 0.85, size=n))

    # Exercicios inadimplentes nos ultimos 5 anos.
    prob_exercicio = 1 / (1 + np.exp(-propensao))
    exercicios_inadimplentes = rng.binomial(5, prob_exercicio * 0.55)

    tem_divida = exercicios_inadimplentes > 0
    tempo_inadimplencia = np.where(
        tem_divida, (rng.gamma(2.0, 260, size=n) * (1 + 0.35 * exercicios_inadimplentes)).round(0), 0
    ).astype(int)

    valor_divida = np.where(
        tem_divida,
        (valor_iptu * exercicios_inadimplentes * rng.normal(1.25, 0.18, size=n)).clip(50, None).round(2),
        0.0,
    )

    qtd_parcelamentos = np.where(tem_divida, rng.poisson(0.55, size=n), 0)
    parcelamento_rompido = ((qtd_parcelamentos > 0) & (rng.random(n) < 0.42)).astype(int)
    qtd_notificacoes = np.where(tem_divida, rng.poisson(1.3 + 0.4 * exercicios_inadimplentes), 0)

    # ---------------- Grupo protegido: IPTU Social ----------------
    # Isencao para idosos, aposentados, pensionistas e PCD de baixa renda.
    # Concentra-se em setores de renda baixa e imoveis de menor valor.
    chance_social = np.where(renda == "baixa", 0.16, np.where(renda == "media", 0.05, 0.01))
    chance_social = chance_social * (valor_venal < np.quantile(valor_venal, 0.55))
    iptu_social = (rng.random(n) < chance_social).astype(int)

    # ---------------- Alvo 1: inadimplencia no proximo exercicio ----------------
    logito_inad = (-1.15
                   + 0.62 * exercicios_inadimplentes
                   + 0.55 * parcelamento_rompido
                   + 0.35 * (tipo_imovel == "terreno")
                   + 0.30 * np.where(renda == "baixa", 1.0, np.where(renda == "media", 0.3, 0.0))
                   + 0.28 * carga_relativa
                   + 0.012 * distancia_centro
                   - 0.22 * np.log1p(valor_venal / 1e5)
                   + rng.normal(0, 0.55, size=n))
    inadimplente = (rng.random(n) < 1 / (1 + np.exp(-logito_inad))).astype(int)

    # ---------------- Alvo 2: recuperacao da divida em 12 meses ----------------
    # So faz sentido para quem tem divida inscrita.
    logito_rec = (1.05
                  - 0.0011 * tempo_inadimplencia
                  - 0.40 * np.log1p(valor_divida / 1000)
                  + 0.70 * (qtd_parcelamentos > 0)
                  - 0.85 * parcelamento_rompido
                  + 0.30 * np.where(renda == "alta", 1.0, np.where(renda == "media", 0.4, 0.0))
                  + 0.18 * np.log1p(valor_venal / 1e5)
                  + rng.normal(0, 0.70, size=n))
    recuperado = np.where(tem_divida,
                          (rng.random(n) < 1 / (1 + np.exp(-logito_rec))).astype(int), 0)

    carteira = pd.DataFrame({
        "id_contribuinte": [_pseudonimizar(i) for i in range(n)],
        "setor_urbano": setores["setor_urbano"],
        "faixa_renda_setor": renda,
        "tipo_imovel": tipo_imovel,
        "area_construida_m2": area,
        "valor_venal": valor_venal,
        "valor_iptu_anual": valor_iptu,
        "distancia_centro_km": distancia_centro,
        "exercicios_inadimplentes_5a": exercicios_inadimplentes,
        "tempo_inadimplencia_dias": tempo_inadimplencia,
        "valor_divida_consolidada": valor_divida,
        "qtd_parcelamentos_anteriores": qtd_parcelamentos,
        "parcelamento_rompido": parcelamento_rompido,
        "qtd_notificacoes": qtd_notificacoes,
        "iptu_social": iptu_social,
        "inadimplente_proximo_exercicio": inadimplente,
        "divida_recuperada_12m": recuperado,
    })

    return _calibrar_pelos_agregados(carteira)


def _calibrar_pelos_agregados(carteira: pd.DataFrame) -> pd.DataFrame:
    """Reescala os valores monetarios para bater com os totais oficiais da Sefin.

    A amostra do PoC tem TAMANHO_AMOSTRA imoveis; o municipio tem
    IMOVEIS_TRIBUTAVEIS. A divida ativa de IPTU proporcional a amostra deve
    aproximar DIVIDA_IPTU * (amostra / total de imoveis).
    """
    proporcao = len(carteira) / config.IMOVEIS_TRIBUTAVEIS
    alvo = config.DIVIDA_IPTU * proporcao
    atual = carteira["valor_divida_consolidada"].sum()

    if atual > 0:
        escala = alvo / atual
        for coluna in ("valor_venal", "valor_iptu_anual", "valor_divida_consolidada"):
            carteira[coluna] = (carteira[coluna] * escala).round(2)

    return carteira


def gerar(forcar: bool = False) -> pd.DataFrame:
    """Gera (ou recupera do cache) a carteira de contribuintes."""
    if config.CSV_CARTEIRA.exists() and not forcar:
        print(f"Usando cache: {config.CSV_CARTEIRA.name}")
        return pd.read_csv(config.CSV_CARTEIRA, sep=";")

    carteira = gerar_carteira()
    carteira.to_csv(config.CSV_CARTEIRA, sep=";", index=False, encoding="utf-8-sig")
    print(f"  carteira sintetica: {len(carteira)} contribuintes -> {config.CSV_CARTEIRA.name}")
    return carteira


if __name__ == "__main__":
    df = gerar(forcar=True)
    print(df.head())
    print("\nTaxa de inadimplencia por faixa de renda do setor:")
    print(df.groupby("faixa_renda_setor")["inadimplente_proximo_exercicio"].mean().round(3))
