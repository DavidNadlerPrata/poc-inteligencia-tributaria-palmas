"""Testes da avaliacao da fila: comparacao com regras simples e prescricao."""

from __future__ import annotations

import pandas as pd
import pytest

import config
import priorizacao

DIA = priorizacao.DIAS_POR_ANO


class TestAlertaDePrescricao:

    @pytest.mark.parametrize("anos, esperado", [
        (0, ""),
        (3.99, ""),
        (4.0, priorizacao.ALERTA_PROXIMA),
        (4.99, priorizacao.ALERTA_PROXIMA),
        (5.0, priorizacao.ALERTA_VENCIDA),
        (12, priorizacao.ALERTA_VENCIDA),
    ])
    def test_fronteiras(self, anos, esperado):
        dias = pd.Series([anos * DIA])
        assert priorizacao.alerta_prescricao(dias).iloc[0] == esperado

    def test_fila_traz_o_alerta(self, fila_cobranca):
        esperado = priorizacao.alerta_prescricao(fila_cobranca["tempo_inadimplencia_dias"])
        assert (fila_cobranca["alerta_prescricao"] == esperado).all()

    def test_resumo_conta_e_localiza(self):
        # 10 dividas na ordem da fila; as duas ultimas prescrevem em ate 12 meses.
        fila = pd.DataFrame({"tempo_inadimplencia_dias": [100] * 8 + [4.5 * DIA] * 2,
                             "valor_divida_consolidada": [1_000.0] * 10})
        resumo = priorizacao.resumo_prescricao(fila)
        proxima = resumo[priorizacao.ALERTA_PROXIMA]
        assert proxima["casos"] == 2
        assert proxima["divida_reais"] == 2_000.0
        assert proxima["no_topo_20pct"] == 0
        assert proxima["posicao_mediana_na_fila"] == pytest.approx(0.95)
        # Percentuais com a base no nome: 2 de 10 dividas, R$ 2 mil de R$ 10 mil.
        assert proxima["percentual_dos_casos_da_fila"] == pytest.approx(0.2)
        assert proxima["percentual_da_divida_da_fila"] == pytest.approx(0.2)
        assert resumo[priorizacao.ALERTA_VENCIDA]["casos"] == 0


def teste_construido() -> pd.DataFrame:
    """Quatro dividas com resultado conhecido.

    Recuperadas: a de 100 e a de 10. Total recuperado: 110.
    Modelo (divida x prob): 100x0,9=90 | 1000x0,05=50 | 10x0,8=8 | 50x0,1=5
    """
    return pd.DataFrame({
        "valor_divida_consolidada": [100.0, 1_000.0, 10.0, 50.0],
        "y_prob": [0.9, 0.05, 0.8, 0.1],
        "y_real": [1, 0, 1, 0],
        "tempo_inadimplencia_dias": [400, 3_000, 100, 900],
    })


class TestComparacaoDeOrdenacoes:

    def test_captura_calculada_a_mao(self):
        teste = teste_construido()
        resumo = priorizacao.resumo_comparacao(teste)
        # Primeiros 50% (2 casos):
        #  modelo -> 100 e 1000: recupera 100 de 110
        #  maiores dividas -> 1000 e 100: recupera 100 de 110
        #  mais recentes -> 10 (100 dias) e 100 (400 dias): recupera 110 de 110
        #  probabilidade -> 100 (0,9) e 10 (0,8): recupera 110 de 110
        assert resumo["modelo"]["50pct"] == pytest.approx(100 / 110, abs=1e-4)
        assert resumo["maiores_dividas"]["50pct"] == pytest.approx(100 / 110, abs=1e-4)
        assert resumo["mais_recentes"]["50pct"] == pytest.approx(1.0)
        assert resumo["probabilidade"]["50pct"] == pytest.approx(1.0)

    def test_curvas_comecam_em_zero_terminam_em_um_e_nao_descem(self):
        curvas = priorizacao.curvas_de_captura(teste_construido(), pontos=20)
        for nome in [*priorizacao.ORDENACOES, "aleatoria"]:
            assert curvas[nome].iloc[0] == 0
            assert curvas[nome].iloc[-1] == pytest.approx(1.0)
            assert curvas[nome].is_monotonic_increasing

    def test_bootstrap_reprodutivel_e_contem_a_estimativa(self, ambiente_treinado):
        teste = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")
        primeira = priorizacao.diferenca_bootstrap(teste, n_reamostras=200, semente=3)
        assert primeira == priorizacao.diferenca_bootstrap(teste, n_reamostras=200, semente=3)
        assert primeira["ic_inferior"] <= primeira["diferenca"] <= primeira["ic_superior"]

    def test_fila_do_modelo_supera_a_ordem_aleatoria(self, ambiente_treinado):
        """Sem isto, a fila nao serviria para nada: trabalhar 20% dos casos
        precisa render bem mais que 20% do valor recuperado."""
        teste = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")
        resumo = priorizacao.resumo_comparacao(teste)
        assert resumo["modelo"]["20pct"] > 0.30

    def test_pacote_do_pipeline(self, ambiente_treinado):
        teste = pd.read_csv(config.DADOS / "teste_recuperabilidade.csv", sep=";")
        pacote = priorizacao.comparar_ordenacoes(teste)
        assert pacote["n_casos"] == len(teste)
        assert set(pacote["resumo"]) == set(priorizacao.ORDENACOES)
        assert len(pacote["curvas"]["fracao_casos"]) == 101

    def test_ordenacao_desconhecida(self):
        with pytest.raises(ValueError):
            priorizacao._chave_de_ordenacao(teste_construido(), "sorteio")
