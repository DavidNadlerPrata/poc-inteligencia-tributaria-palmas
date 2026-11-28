"""Testes das metricas de justica algoritmica.

As formulas sao verificadas contra casos construidos a mao, com resultado
conhecido por calculo direto. Uma metrica de fairness errada e pior que nenhuma:
produz um laudo de conformidade falso.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fairness


def montar(grupos, reais, previstos) -> pd.DataFrame:
    return pd.DataFrame({"faixa_renda_setor": grupos, "y_real": reais, "y_pred": previstos})


class TestParidadeDemografica:
    """DPD = max_a P(Y_pred=1|A=a) - min_a P(Y_pred=1|A=a)"""

    def test_paridade_perfeita_da_zero(self):
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 0, 1, 0, 1, 0, 1, 0],
                       [1, 0, 1, 0, 1, 0, 1, 0])  # 50% em ambos
        resultado = fairness.paridade_demografica(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        assert resultado["diferenca"] == 0.0
        assert resultado["razao"] == 1.0
        assert resultado["aprovado"]

    def test_disparidade_maxima_da_um(self):
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 0, 0, 1, 1, 0, 0],
                       [1, 1, 1, 1, 0, 0, 0, 0])  # 100% vs 0%
        resultado = fairness.paridade_demografica(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        assert resultado["diferenca"] == 1.0
        assert not resultado["aprovado"]

    def test_valor_intermediario_calculado_a_mao(self):
        # grupo a: 3 de 4 selecionados = 0,75 | grupo b: 1 de 4 = 0,25
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 1, 0, 1, 0, 0, 0],
                       [1, 1, 1, 0, 1, 0, 0, 0])
        resultado = fairness.paridade_demografica(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        assert resultado["diferenca"] == pytest.approx(0.50)
        assert resultado["razao"] == pytest.approx(0.3333, abs=1e-4)
        assert resultado["grupo_mais_selecionado"] == "a"
        assert resultado["grupo_menos_selecionado"] == "b"

    def test_limite_de_disparidade_e_dez_por_cento(self):
        """O limite 0,10 e a convencao do AI Fairness 360 (Bellamy et al., 2019)."""
        assert fairness.LIMITE_DISPARIDADE == 0.10


class TestIgualdadeOportunidade:
    """EOD = max_a TPR_a - min_a TPR_a (recall por grupo)"""

    def test_recall_identico_da_zero(self):
        # ambos os grupos acertam 1 dos 2 positivos
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 0, 0, 1, 1, 0, 0],
                       [1, 0, 0, 0, 1, 0, 0, 0])
        resultado = fairness.igualdade_oportunidade(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        assert resultado["diferenca"] == 0.0
        assert resultado["aprovado"]

    def test_recall_muito_diferente_reprova(self):
        # grupo a: acerta 2 de 2 (TPR 1,0) | grupo b: acerta 0 de 2 (TPR 0,0)
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 0, 0, 1, 1, 0, 0],
                       [1, 1, 0, 0, 0, 0, 0, 0])
        resultado = fairness.igualdade_oportunidade(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        assert resultado["diferenca"] == 1.0
        assert not resultado["aprovado"]
        assert resultado["grupo_melhor_atendido"] == "a"
        assert resultado["grupo_pior_atendido"] == "b"

    def test_recall_ignora_os_negativos(self):
        """TPR e condicionado a Y=1: mudar predicao de negativo nao o altera."""
        base = montar(["a"] * 4, [1, 1, 0, 0], [1, 0, 0, 0])
        alterado = montar(["a"] * 4, [1, 1, 0, 0], [1, 0, 1, 1])
        tpr_base = fairness.metricas_por_grupo(base, "faixa_renda_setor")["tpr_recall"][0]
        tpr_alterado = fairness.metricas_por_grupo(alterado, "faixa_renda_setor")["tpr_recall"][0]
        assert tpr_base == tpr_alterado == 0.5


class TestMetricasPorGrupo:

    def test_colunas_do_laudo(self, ):
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 0, 0, 1, 0, 0, 0],
                       [1, 0, 1, 0, 1, 1, 0, 0])
        por_grupo = fairness.metricas_por_grupo(dados, "faixa_renda_setor")
        esperadas = {"grupo", "n", "prevalencia_real", "taxa_selecao",
                     "tpr_recall", "fpr", "precisao"}
        assert esperadas <= set(por_grupo.columns)

    def test_contagem_por_grupo(self):
        dados = montar(["a"] * 5 + ["b"] * 3, [1] * 8, [1] * 8)
        por_grupo = fairness.metricas_por_grupo(dados, "faixa_renda_setor")
        assert por_grupo.set_index("grupo").loc["a", "n"] == 5
        assert por_grupo.set_index("grupo").loc["b", "n"] == 3

    def test_grupo_sem_positivos_nao_quebra(self):
        """Grupo so com negativos: TPR indefinido, e isso nao pode virar erro."""
        dados = montar(["a"] * 3 + ["b"] * 3, [0, 0, 0, 1, 1, 0], [0, 1, 0, 1, 1, 0])
        por_grupo = fairness.metricas_por_grupo(dados, "faixa_renda_setor")
        assert np.isnan(por_grupo.set_index("grupo").loc["a", "tpr_recall"])


class TestMitigacao:
    """Corte calibrado por grupo (Hardt, Price e Srebro, 2016)."""

    @pytest.fixture
    def dados_enviesados(self):
        rng = np.random.default_rng(42)
        n = 600
        grupos = rng.choice(["alta", "baixa"], size=n)
        # grupo 'baixa' recebe scores sistematicamente mais altos
        prob = np.where(grupos == "baixa",
                        rng.beta(6, 3, size=n), rng.beta(3, 6, size=n))
        real = (rng.random(n) < prob).astype(int)
        return pd.DataFrame({"faixa_renda_setor": grupos, "y_prob": prob, "y_real": real})

    def test_mitigacao_reduz_a_disparidade(self, dados_enviesados):
        resultado = fairness.simular_mitigacao(dados_enviesados)
        antes = resultado["taxa_selecao_antes"]
        depois = resultado["taxa_selecao_depois"]
        assert (depois.max() - depois.min()) < (antes.max() - antes.min())

    def test_taxas_ficam_praticamente_iguais(self, dados_enviesados):
        resultado = fairness.simular_mitigacao(dados_enviesados)
        depois = resultado["taxa_selecao_depois"]
        assert (depois.max() - depois.min()) < 0.02

    def test_cortes_sao_registrados_por_grupo(self, dados_enviesados):
        """Auditabilidade: o corte de cada grupo precisa ser explicito."""
        resultado = fairness.simular_mitigacao(dados_enviesados)
        assert "corte_calibrado" in resultado.columns
        assert len(resultado) == 2
        assert resultado["corte_calibrado"].notna().all()


class TestAuditoriaCompleta:

    def test_auditar_devolve_os_dois_testes(self):
        dados = montar(["a"] * 6 + ["b"] * 6,
                       [1, 1, 0, 0, 1, 0] * 2,
                       [1, 0, 1, 0, 1, 0] * 2)
        resultado = fairness.auditar(dados)
        assert set(resultado) == {"por_grupo", "paridade_demografica",
                                  "igualdade_oportunidade"}

    def test_veredito_e_booleano_serializavel(self):
        """O laudo vai para JSON; numpy.bool_ quebraria a serializacao."""
        dados = montar(["a"] * 4 + ["b"] * 4,
                       [1, 1, 0, 0] * 2, [1, 0, 1, 0] * 2)
        resultado = fairness.auditar(dados)
        for teste in ("paridade_demografica", "igualdade_oportunidade"):
            assert isinstance(resultado[teste]["aprovado"], bool)


class TestIntervaloBootstrap:
    """Incerteza de amostragem das diferencas, por bootstrap dentro de cada grupo."""

    @staticmethod
    def carteira(taxa_a: float, taxa_b: float, n: int, semente: int = 1) -> pd.DataFrame:
        rng = np.random.default_rng(semente)
        real = rng.integers(0, 2, size=2 * n)
        pred = np.concatenate([rng.random(n) < taxa_a, rng.random(n) < taxa_b]).astype(int)
        return montar(["a"] * n + ["b"] * n, real, pred)

    def test_intervalo_contem_a_estimativa_pontual(self):
        resultado = fairness.intervalo_bootstrap(self.carteira(0.6, 0.45, 300), n_reamostras=500)
        for nome in ("paridade_demografica", "igualdade_oportunidade"):
            bloco = resultado[nome]
            assert bloco["ic_inferior"] <= bloco["diferenca"] <= bloco["ic_superior"]

    def test_estimativa_pontual_e_a_mesma_da_auditoria(self):
        dados = self.carteira(0.6, 0.45, 300)
        auditoria = fairness.paridade_demografica(
            fairness.metricas_por_grupo(dados, "faixa_renda_setor"))
        resultado = fairness.intervalo_bootstrap(dados, n_reamostras=200)
        assert resultado["paridade_demografica"]["diferenca"] == auditoria["diferenca"]

    def test_reprodutivel_com_a_mesma_semente(self):
        dados = self.carteira(0.6, 0.45, 300)
        assert (fairness.intervalo_bootstrap(dados, n_reamostras=300, semente=7)
                == fairness.intervalo_bootstrap(dados, n_reamostras=300, semente=7))

    def test_mais_casos_estreitam_o_intervalo(self):
        def largura(n):
            bloco = fairness.intervalo_bootstrap(self.carteira(0.6, 0.45, n),
                                                 n_reamostras=500)["paridade_demografica"]
            return bloco["ic_superior"] - bloco["ic_inferior"]
        assert largura(4_000) < largura(200) / 3

    def test_disparidade_clara_fica_toda_acima_do_limite(self):
        resultado = fairness.intervalo_bootstrap(self.carteira(0.8, 0.2, 500), n_reamostras=500)
        assert resultado["paridade_demografica"]["ic_inferior"] > fairness.LIMITE_DISPARIDADE
        assert resultado["paridade_demografica"]["prob_acima_do_limite"] == 1.0

    def test_grupos_iguais_ficam_abaixo_do_limite(self):
        resultado = fairness.intervalo_bootstrap(self.carteira(0.5, 0.5, 5_000), n_reamostras=500)
        assert resultado["paridade_demografica"]["ic_superior"] < fairness.LIMITE_DISPARIDADE
