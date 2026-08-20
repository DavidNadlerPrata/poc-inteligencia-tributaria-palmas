"""Pipeline ETL: extrai, transforma e carrega os dados no banco relacional.

Cobre a Sprint 1 (Banco de Dados - Modulo 4) e a Sprint 2 (ETL - Modulo 5).

Modelo relacional (3FN):

    setor_urbano (1) ----< imovel (1) ----< divida_ativa
                                 |
                                 +--------< historico_cobranca

    arrecadacao_mensal  -- serie agregada real vinda da API

O banco e SQLite para manter o PoC executavel sem servidor. A migracao para
PostgreSQL exige apenas trocar a string de conexao: o DDL usa apenas tipos e
restricoes padrao SQL.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

import config

DDL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS historico_cobranca;
DROP TABLE IF EXISTS divida_ativa;
DROP TABLE IF EXISTS imovel;
DROP TABLE IF EXISTS setor_urbano;
DROP TABLE IF EXISTS arrecadacao_mensal;

CREATE TABLE setor_urbano (
    id_setor           INTEGER PRIMARY KEY,
    nome               TEXT    NOT NULL UNIQUE,
    faixa_renda        TEXT    NOT NULL CHECK (faixa_renda IN ('baixa','media','alta'))
);

CREATE TABLE imovel (
    id_imovel          INTEGER PRIMARY KEY,
    id_contribuinte    TEXT    NOT NULL UNIQUE,   -- pseudonimizado (LGPD Art. 13)
    id_setor           INTEGER NOT NULL,
    tipo_imovel        TEXT    NOT NULL,
    area_construida_m2 REAL    NOT NULL CHECK (area_construida_m2 >= 0),
    valor_venal        REAL    NOT NULL CHECK (valor_venal > 0),
    valor_iptu_anual   REAL    NOT NULL CHECK (valor_iptu_anual >= 0),
    distancia_centro_km REAL   NOT NULL,
    iptu_social        INTEGER NOT NULL DEFAULT 0 CHECK (iptu_social IN (0,1)),
    FOREIGN KEY (id_setor) REFERENCES setor_urbano (id_setor)
);

CREATE TABLE divida_ativa (
    id_divida                   INTEGER PRIMARY KEY,
    id_imovel                   INTEGER NOT NULL,
    exercicios_inadimplentes_5a INTEGER NOT NULL,
    tempo_inadimplencia_dias    INTEGER NOT NULL,
    valor_divida_consolidada    REAL    NOT NULL,
    divida_recuperada_12m       INTEGER NOT NULL CHECK (divida_recuperada_12m IN (0,1)),
    FOREIGN KEY (id_imovel) REFERENCES imovel (id_imovel)
);

CREATE TABLE historico_cobranca (
    id_historico                 INTEGER PRIMARY KEY,
    id_imovel                    INTEGER NOT NULL,
    qtd_parcelamentos_anteriores INTEGER NOT NULL,
    parcelamento_rompido         INTEGER NOT NULL CHECK (parcelamento_rompido IN (0,1)),
    qtd_notificacoes             INTEGER NOT NULL,
    inadimplente_proximo_exercicio INTEGER NOT NULL CHECK (inadimplente_proximo_exercicio IN (0,1)),
    FOREIGN KEY (id_imovel) REFERENCES imovel (id_imovel)
);

CREATE TABLE arrecadacao_mensal (
    id_arrecadacao         INTEGER PRIMARY KEY,
    codigo                 TEXT,
    descricao              TEXT,
    orgao_nome             TEXT,
    ano                    INTEGER,
    mes                    INTEGER,
    valor_orcado           REAL,
    valor_arrecado_mes     REAL,
    valor_arrecado_periodo REAL
);

CREATE INDEX idx_imovel_setor      ON imovel (id_setor);
CREATE INDEX idx_divida_imovel     ON divida_ativa (id_imovel);
CREATE INDEX idx_historico_imovel  ON historico_cobranca (id_imovel);
CREATE INDEX idx_arrecadacao_per   ON arrecadacao_mensal (ano, mes);
"""


def _limpar_arrecadacao(bruto: pd.DataFrame) -> pd.DataFrame:
    """Transforma a resposta crua da API em tabela tipada e sem duplicatas.

    A listagem do portal traz TODOS os niveis da hierarquia de receitas
    ("RECEITAS CORRENTES" agrega as subcategorias abaixo dela). Somar tudo
    contaria o mesmo dinheiro varias vezes, entao marcamos o nivel hierarquico
    a partir do codigo para permitir filtrar depois.
    """
    df = bruto.copy()

    colunas = ["codigo", "descricao", "orgao_nome", "ano", "mes",
               "valor_orcado", "valor_arrecado_mes", "valor_arrecado_periodo"]
    df = df[[c for c in colunas if c in df.columns]].copy()

    for coluna in ("ano", "mes"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Int64")

    for coluna in ("valor_orcado", "valor_arrecado_mes", "valor_arrecado_periodo"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)

    df["descricao"] = df["descricao"].astype(str).str.strip().str.upper()
    df = df.drop_duplicates()
    df = df[df["ano"].notna()]

    return df


def _dividir_carteira(carteira: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Normaliza a carteira plana nas tabelas do modelo relacional (3FN)."""
    setores = (carteira[["setor_urbano", "faixa_renda_setor"]]
               .drop_duplicates()
               .reset_index(drop=True)
               .rename(columns={"setor_urbano": "nome", "faixa_renda_setor": "faixa_renda"}))
    setores["id_setor"] = setores.index + 1

    mapa_setor = dict(zip(setores["nome"], setores["id_setor"], strict=True))

    base = carteira.reset_index(drop=True).copy()
    base["id_imovel"] = base.index + 1
    base["id_setor"] = base["setor_urbano"].map(mapa_setor)

    imoveis = base[["id_imovel", "id_contribuinte", "id_setor", "tipo_imovel",
                    "area_construida_m2", "valor_venal", "valor_iptu_anual",
                    "distancia_centro_km", "iptu_social"]]

    dividas = base[base["valor_divida_consolidada"] > 0][
        ["id_imovel", "exercicios_inadimplentes_5a", "tempo_inadimplencia_dias",
         "valor_divida_consolidada", "divida_recuperada_12m"]
    ].reset_index(drop=True)
    dividas.insert(0, "id_divida", dividas.index + 1)

    historico = base[["id_imovel", "qtd_parcelamentos_anteriores", "parcelamento_rompido",
                      "qtd_notificacoes", "inadimplente_proximo_exercicio"]].reset_index(drop=True)
    historico.insert(0, "id_historico", historico.index + 1)

    return {"setor_urbano": setores[["id_setor", "nome", "faixa_renda"]],
            "imovel": imoveis,
            "divida_ativa": dividas,
            "historico_cobranca": historico}


def executar(carteira: pd.DataFrame, arrecadacao: pd.DataFrame | None = None) -> None:
    """Roda o ETL completo e materializa o banco."""
    print("ETL: criando esquema...")
    conexao = sqlite3.connect(config.BANCO)
    try:
        conexao.executescript(DDL)

        tabelas = _dividir_carteira(carteira)
        for nome, tabela in tabelas.items():
            tabela.to_sql(nome, conexao, if_exists="append", index=False)
            print(f"  {nome}: {len(tabela)} linhas")

        if arrecadacao is not None and not arrecadacao.empty:
            limpa = _limpar_arrecadacao(arrecadacao)
            limpa.to_sql("arrecadacao_mensal", conexao, if_exists="append", index=False)
            print(f"  arrecadacao_mensal: {len(limpa)} linhas (dados reais da API)")

        conexao.commit()
    finally:
        conexao.close()

    print(f"ETL concluido -> {config.BANCO.name}")


def consultar(sql: str, parametros: tuple = ()) -> pd.DataFrame:
    """Executa uma consulta e devolve o resultado como DataFrame."""
    conexao = sqlite3.connect(config.BANCO)
    try:
        return pd.read_sql_query(sql, conexao, params=parametros)
    finally:
        conexao.close()


# Consulta usada pelo treino e pelo painel: junta as tres tabelas do cadastro.
SQL_VISAO_ANALITICA = """
SELECT  i.id_contribuinte,
        s.nome              AS setor_urbano,
        s.faixa_renda       AS faixa_renda_setor,
        i.tipo_imovel,
        i.area_construida_m2,
        i.valor_venal,
        i.valor_iptu_anual,
        i.distancia_centro_km,
        i.iptu_social,
        COALESCE(d.exercicios_inadimplentes_5a, 0) AS exercicios_inadimplentes_5a,
        COALESCE(d.tempo_inadimplencia_dias, 0)    AS tempo_inadimplencia_dias,
        COALESCE(d.valor_divida_consolidada, 0)    AS valor_divida_consolidada,
        COALESCE(d.divida_recuperada_12m, 0)       AS divida_recuperada_12m,
        h.qtd_parcelamentos_anteriores,
        h.parcelamento_rompido,
        h.qtd_notificacoes,
        h.inadimplente_proximo_exercicio
FROM        imovel             i
JOIN        setor_urbano       s ON s.id_setor  = i.id_setor
JOIN        historico_cobranca h ON h.id_imovel = i.id_imovel
LEFT JOIN   divida_ativa       d ON d.id_imovel = i.id_imovel
"""


def carregar_visao_analitica() -> pd.DataFrame:
    return consultar(SQL_VISAO_ANALITICA)


if __name__ == "__main__":
    import sintetico
    executar(sintetico.gerar())
    print(carregar_visao_analitica().head())
