"""Testes do gerador sintetico e do pipeline ETL.

Cobrem a qualidade da base analitica: reprodutibilidade, calibracao pelos
agregados oficiais, integridade referencial do banco e limpeza da arrecadacao.
"""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

import config
import etl
import sintetico


class TestGeradorSintetico:

    def test_tamanho_solicitado(self, carteira):
        assert len(carteira) == 3_000

    def test_reprodutibilidade_com_a_mesma_semente(self):
        primeira = sintetico.gerar_carteira(n=500, semente=7)
        segunda = sintetico.gerar_carteira(n=500, semente=7)
        pd.testing.assert_frame_equal(primeira, segunda)

    def test_sementes_diferentes_geram_carteiras_diferentes(self):
        primeira = sintetico.gerar_carteira(n=500, semente=7)
        segunda = sintetico.gerar_carteira(n=500, semente=8)
        assert not primeira["valor_venal"].equals(segunda["valor_venal"])

    def test_colunas_esperadas(self, carteira):
        esperadas = {
            "id_contribuinte", "setor_urbano", "faixa_renda_setor", "tipo_imovel",
            "area_construida_m2", "valor_venal", "valor_iptu_anual",
            "distancia_centro_km", "exercicios_inadimplentes_5a",
            "tempo_inadimplencia_dias", "valor_divida_consolidada",
            "qtd_parcelamentos_anteriores", "parcelamento_rompido",
            "qtd_notificacoes", "iptu_social", "inadimplente_proximo_exercicio",
            "divida_recuperada_12m",
        }
        assert esperadas == set(carteira.columns)

    def test_sem_valores_ausentes(self, carteira):
        assert not carteira.isna().any().any()

    @pytest.mark.parametrize("coluna", [
        "valor_venal", "valor_iptu_anual", "valor_divida_consolidada",
        "area_construida_m2", "distancia_centro_km", "tempo_inadimplencia_dias",
    ])
    def test_grandezas_nao_sao_negativas(self, carteira, coluna):
        assert (carteira[coluna] >= 0).all()

    def test_valor_venal_e_sempre_positivo(self, carteira):
        """O DDL do banco exige valor_venal > 0."""
        assert (carteira["valor_venal"] > 0).all()

    @pytest.mark.parametrize("coluna", [
        "parcelamento_rompido", "iptu_social",
        "inadimplente_proximo_exercicio", "divida_recuperada_12m",
    ])
    def test_indicadores_sao_binarios(self, carteira, coluna):
        assert set(carteira[coluna].unique()) <= {0, 1}

    def test_exercicios_inadimplentes_no_intervalo(self, carteira):
        assert carteira["exercicios_inadimplentes_5a"].between(0, 5).all()

    def test_terreno_nao_tem_area_construida(self, carteira):
        terrenos = carteira[carteira["tipo_imovel"] == "terreno"]
        assert (terrenos["area_construida_m2"] == 0).all()

    def test_faixas_de_renda_validas(self, carteira):
        assert set(carteira["faixa_renda_setor"].unique()) <= {"baixa", "media", "alta"}


class TestCoerenciaDaDivida:
    """Sem divida inscrita, tudo que dela decorre precisa ser zero."""

    def test_sem_exercicios_inadimplentes_nao_ha_divida(self, carteira):
        adimplentes = carteira[carteira["exercicios_inadimplentes_5a"] == 0]
        assert (adimplentes["valor_divida_consolidada"] == 0).all()
        assert (adimplentes["tempo_inadimplencia_dias"] == 0).all()

    def test_sem_divida_nao_ha_recuperacao(self, carteira):
        sem_divida = carteira[carteira["valor_divida_consolidada"] == 0]
        assert (sem_divida["divida_recuperada_12m"] == 0).all()

    def test_quem_tem_divida_tem_exercicios_inadimplentes(self, carteira):
        com_divida = carteira[carteira["valor_divida_consolidada"] > 0]
        assert (com_divida["exercicios_inadimplentes_5a"] > 0).all()


class TestCalibracao:
    """A carteira precisa refletir os agregados oficiais da Sefin."""

    def test_divida_proporcional_ao_total_do_municipio(self):
        carteira = sintetico.gerar_carteira(n=5_000, semente=config.SEMENTE)
        proporcao = len(carteira) / config.IMOVEIS_TRIBUTAVEIS
        alvo = config.DIVIDA_IPTU * proporcao
        obtido = carteira["valor_divida_consolidada"].sum()
        assert obtido == pytest.approx(alvo, rel=0.01)

    def test_vies_social_esta_presente(self, carteira):
        """O vies deliberado precisa existir: sem ele a Sprint 4 fica vazia."""
        por_renda = carteira.groupby("faixa_renda_setor")["inadimplente_proximo_exercicio"].mean()
        assert por_renda["baixa"] > por_renda["media"] > por_renda["alta"]


class TestEsquemaDoBanco:

    def test_tabelas_criadas(self, carteira, banco_temporario):
        etl.executar(carteira)
        conexao = sqlite3.connect(banco_temporario)
        try:
            nomes = {linha[0] for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conexao.close()
        assert {"setor_urbano", "imovel", "divida_ativa",
                "historico_cobranca", "arrecadacao_mensal"} <= nomes

    def test_integridade_referencial(self, carteira, banco_temporario):
        """Nenhuma chave estrangeira orfa."""
        etl.executar(carteira)
        conexao = sqlite3.connect(banco_temporario)
        try:
            conexao.execute("PRAGMA foreign_keys = ON")
            violacoes = conexao.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            conexao.close()
        assert violacoes == []

    def test_divida_ativa_so_para_quem_tem_divida(self, carteira, banco_temporario):
        etl.executar(carteira)
        esperado = int((carteira["valor_divida_consolidada"] > 0).sum())
        total = etl.consultar("SELECT COUNT(*) AS n FROM divida_ativa")["n"][0]
        assert total == esperado

    def test_um_historico_por_imovel(self, carteira, banco_temporario):
        etl.executar(carteira)
        imoveis = etl.consultar("SELECT COUNT(*) AS n FROM imovel")["n"][0]
        historicos = etl.consultar("SELECT COUNT(*) AS n FROM historico_cobranca")["n"][0]
        assert imoveis == historicos == len(carteira)

    def test_setores_normalizados_sem_repeticao(self, carteira, banco_temporario):
        """3FN: o setor aparece uma vez na sua tabela, nao repetido por imovel."""
        etl.executar(carteira)
        setores = etl.consultar("SELECT COUNT(*) AS n FROM setor_urbano")["n"][0]
        assert setores == carteira["setor_urbano"].nunique()
        assert setores < len(carteira)


class TestVisaoAnalitica:

    def test_preserva_todos_os_contribuintes(self, carteira, base_analitica):
        """O LEFT JOIN com divida_ativa nao pode perder quem nao tem divida."""
        assert len(base_analitica) == len(carteira)

    def test_sem_divida_vira_zero_e_nao_nulo(self, base_analitica):
        assert base_analitica["valor_divida_consolidada"].notna().all()
        assert (base_analitica["valor_divida_consolidada"] >= 0).all()

    def test_totais_batem_com_a_carteira(self, carteira, base_analitica):
        assert base_analitica["valor_divida_consolidada"].sum() == pytest.approx(
            carteira["valor_divida_consolidada"].sum(), rel=1e-6)
        assert base_analitica["iptu_social"].sum() == carteira["iptu_social"].sum()


class TestLimpezaDaArrecadacao:
    """Transformacao dos dados reais vindos da API."""

    @pytest.fixture
    def bruto(self):
        return pd.DataFrame({
            "codigo": ["1.0.0.0.00.0.0", "1.1.0.0.00.0.0", "1.1.0.0.00.0.0"],
            "descricao": [" receitas correntes ", "Impostos", "Impostos"],
            "orgao_nome": ["TESOURO", "TESOURO", "TESOURO"],
            "ano": ["2025", "2025", "2025"],
            "mes": ["7", "7", "7"],
            "valor_orcado": ["1000.50", "", "abc"],
            "valor_arrecado_mes": ["500.25", "300.00", "300.00"],
            "valor_arrecado_periodo": ["500.25", "300.00", "300.00"],
        })

    def test_converte_tipos_textuais(self, bruto):
        limpo = etl._limpar_arrecadacao(bruto)
        assert pd.api.types.is_integer_dtype(limpo["ano"])
        assert pd.api.types.is_float_dtype(limpo["valor_arrecado_mes"])

    def test_normaliza_descricao(self, bruto):
        limpo = etl._limpar_arrecadacao(bruto)
        assert "RECEITAS CORRENTES" in limpo["descricao"].tolist()

    def test_remove_duplicatas(self, bruto):
        limpo = etl._limpar_arrecadacao(bruto)
        assert len(limpo) == 2

    def test_valores_invalidos_viram_zero(self, bruto):
        limpo = etl._limpar_arrecadacao(bruto)
        assert limpo["valor_orcado"].notna().all()
        assert (limpo["valor_orcado"] >= 0).all()
