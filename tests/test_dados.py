"""Testes do gerador sintetico e do pipeline ETL.

Cobrem a qualidade da base analitica: reprodutibilidade, calibracao pelos
agregados oficiais, integridade referencial do banco e limpeza da arrecadacao.
"""

from __future__ import annotations

import sqlite3

import numpy as np
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


class TestCarteiraVersionada:
    """O CSV versionado precisa corresponder ao que o gerador produz hoje.

    A carteira fica no repositorio para que se possa abri-la direto, sem rodar
    o pipeline. Isso cria um risco: alguem ajusta os parametros do gerador, nao
    regenera o arquivo, e o PoC passa a rodar sobre dados que nao correspondem
    ao codigo -- uma divergencia silenciosa, que nenhum outro teste pegaria.

    Para corrigir uma falha aqui:  python -c "import sys; sys.path.insert(0,'src'); import sintetico; sintetico.gerar(forcar=True)"
    """

    @pytest.fixture(scope="class")
    def do_disco(self):
        if not config.CSV_CARTEIRA.exists():
            pytest.skip("carteira versionada ausente; gere com sintetico.gerar()")
        return pd.read_csv(config.CSV_CARTEIRA, sep=";")

    @pytest.fixture(scope="class")
    def recem_gerada(self):
        return sintetico.gerar_carteira()   # tamanho e semente padrao

    def test_mesmo_numero_de_registros(self, do_disco, recem_gerada):
        assert len(do_disco) == len(recem_gerada) == config.TAMANHO_AMOSTRA

    def test_mesmas_colunas_na_mesma_ordem(self, do_disco, recem_gerada):
        assert list(do_disco.columns) == list(recem_gerada.columns)

    def test_conteudo_identico(self, do_disco, recem_gerada):
        """Compara com tolerancia numerica: a ida e volta pelo CSV arredonda
        floats, e o arquivo pode ter sido escrito em outra plataforma."""
        pd.testing.assert_frame_equal(
            do_disco.reset_index(drop=True), recem_gerada.reset_index(drop=True),
            check_dtype=False, rtol=1e-6,
        )

    def test_sem_dado_pessoal(self, do_disco):
        """O arquivo esta publico no repositorio: nada que identifique alguem."""
        proibidos = {"cpf", "cnpj", "nome", "endereco", "email", "telefone",
                     "inscricao_imobiliaria", "matricula"}
        assert not (proibidos & {c.lower() for c in do_disco.columns})
        assert do_disco["id_contribuinte"].str.fullmatch(r"[0-9a-f]{16}").all()


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


@pytest.fixture(scope="module")
def carteira_completa():
    """Carteira no tamanho do PoC: com 20.000 registros, o ruido de amostragem
    das proporcoes fica perto de 0,35 ponto percentual."""
    return sintetico.gerar_carteira()


class TestCalibracaoDosDevedores:
    """Proporcao de devedores, inadimplencia anual e grandezas monetarias.

    As referencias e a hipotese adotada estao em config.py e no Model Card,
    secao 5.
    """

    def test_proporcao_de_devedores(self, carteira_completa):
        obtida = (carteira_completa["valor_divida_consolidada"] > 0).mean()
        assert obtida == pytest.approx(config.PROPORCAO_COM_DIVIDA, abs=0.015)

    def test_inadimplencia_anual(self, carteira_completa):
        obtida = carteira_completa["inadimplente_proximo_exercicio"].mean()
        assert obtida == pytest.approx(config.INADIMPLENCIA_ANUAL, abs=0.015)

    def test_iptu_compativel_com_a_arrecadacao_real(self, carteira_completa):
        """R$ 43 mi pagos a vista por 51.421 contribuintes em 2026 (com desconto)
        dao cerca de R$ 840 por imovel. Reescalar o IPTU junto com a divida, como
        a primeira versao fazia, levaria a media para perto de R$ 5 mil."""
        assert 700 < carteira_completa["valor_iptu_anual"].mean() < 1_400

    def test_encargos_plausiveis(self, carteira_completa):
        """Divida sobre o IPTU dos exercicios em aberto: multa, juros e correcao."""
        devedores = carteira_completa[carteira_completa["valor_divida_consolidada"] > 0]
        principal = (devedores["valor_iptu_anual"] * devedores["exercicios_inadimplentes_5a"]).sum()
        fator = devedores["valor_divida_consolidada"].sum() / principal
        assert 1.5 < fator < 3.0

    def test_devedor_e_recorrente(self, carteira_completa):
        devedores = carteira_completa[carteira_completa["valor_divida_consolidada"] > 0]
        assert devedores["exercicios_inadimplentes_5a"].mean() > 3

    def test_vies_por_renda_sobrevive_a_calibracao(self, carteira_completa):
        tem_divida = carteira_completa["valor_divida_consolidada"] > 0
        por_renda = tem_divida.groupby(carteira_completa["faixa_renda_setor"]).mean()
        assert por_renda["baixa"] > por_renda["media"] > por_renda["alta"]


class TestBisseccao:

    @pytest.mark.parametrize("alvo", [0.10, 0.44, 0.83])
    def test_encontra_o_deslocamento(self, alvo):
        propensao = np.random.default_rng(0).normal(0, 1.2, 5_000)
        deslocamento = sintetico._deslocamento_para_proporcao(propensao, alvo)
        assert sintetico._sigmoide(propensao + deslocamento).mean() == pytest.approx(alvo, abs=1e-9)

    @pytest.mark.parametrize("alvo", [0.0, 1.0, -0.2, 1.5])
    def test_recusa_proporcao_impossivel(self, alvo):
        with pytest.raises(ValueError):
            sintetico._deslocamento_para_proporcao(np.zeros(10), alvo)


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


class TestProbabilidadesVerdadeiras:
    """As chances que o gerador sorteou, usadas para medir o teto de desempenho."""

    @pytest.fixture(scope="class")
    def geradas(self):
        return sintetico.probabilidades_verdadeiras(n=3_000, semente=config.SEMENTE)

    def test_carteira_e_a_mesma_de_gerar_carteira(self, geradas):
        carteira, _ = geradas
        pd.testing.assert_frame_equal(
            carteira, sintetico.gerar_carteira(n=3_000, semente=config.SEMENTE))

    def test_chances_sao_probabilidades_alinhadas_a_carteira(self, geradas):
        carteira, chances = geradas
        assert (chances["id_contribuinte"] == carteira["id_contribuinte"]).all()
        valores = chances.drop(columns="id_contribuinte").to_numpy()
        assert ((valores > 0) & (valores < 1)).all()

    def test_chance_media_de_inadimplencia_e_a_calibrada(self, geradas):
        _, chances = geradas
        assert chances["prob_inadimplencia_com_ruido"].mean() == pytest.approx(
            config.INADIMPLENCIA_ANUAL, abs=1e-6)

    def test_teto_absoluto_supera_o_alcancavel(self):
        teto = sintetico.teto_de_desempenho(n=3_000, semente=config.SEMENTE)
        for nome in ("inadimplencia", "recuperabilidade"):
            assert 0.5 < teto[nome]["alcancavel"]["roc_auc"] < teto[nome]["absoluto"]["roc_auc"] < 1
