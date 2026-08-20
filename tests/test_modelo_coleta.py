"""Testes dos modelos e da camada de coleta.

Os testes de coleta usam dublês de resposta HTTP: a suite nao pode depender de
rede nem sobrecarregar o servidor da Prefeitura a cada execucao.
"""

from __future__ import annotations

import json

import pytest
import requests

import coleta
import config
import modelo


class TestTreino:

    @pytest.fixture
    def metricas(self, metricas_treino):
        return metricas_treino

    def test_treina_os_dois_modelos(self, metricas):
        assert set(metricas) == {"inadimplencia", "recuperabilidade"}

    @pytest.mark.parametrize("nome", ["inadimplencia", "recuperabilidade"])
    def test_metricas_reportadas(self, metricas, nome):
        """O plano de ensino exige acuracia, precisao, recall, F1 e matriz."""
        exigidas = {"acuracia", "precisao", "recall", "f1", "matriz_confusao"}
        assert exigidas <= set(metricas[nome])

    @pytest.mark.parametrize("nome", ["inadimplencia", "recuperabilidade"])
    def test_metricas_no_intervalo_valido(self, metricas, nome):
        for chave in ("acuracia", "precisao", "recall", "f1", "roc_auc"):
            assert 0.0 <= metricas[nome][chave] <= 1.0

    @pytest.mark.parametrize("nome", ["inadimplencia", "recuperabilidade"])
    def test_modelo_supera_o_acaso(self, metricas, nome):
        assert metricas[nome]["roc_auc"] > 0.55, (
            f"{nome} nao aprendeu nada util: ROC-AUC {metricas[nome]['roc_auc']}")

    @pytest.mark.parametrize("nome", ["inadimplencia", "recuperabilidade"])
    def test_desempenho_nao_e_perfeito(self, metricas, nome):
        """ROC-AUC perto de 1,0 aqui indicaria vazamento, nao qualidade."""
        assert metricas[nome]["roc_auc"] < 0.98, (
            f"{nome} suspeito de vazamento de dados")

    def test_matriz_de_confusao_soma_o_conjunto_de_teste(self, metricas):
        for nome in ("inadimplencia", "recuperabilidade"):
            matriz = metricas[nome]["matriz_confusao"]
            assert sum(sum(linha) for linha in matriz) == metricas[nome]["n_teste"]

    def test_modelos_serializados(self, metricas):
        assert config.MODELO_INADIMPLENCIA.exists()
        assert config.MODELO_RECUPERABILIDADE.exists()

    def test_recuperabilidade_treinada_so_com_quem_tem_divida(self, base_treinada, metricas):
        com_divida = base_treinada[(base_treinada["valor_divida_consolidada"] > 0)
                                   & (base_treinada["iptu_social"] == 0)]
        # 25% do universo vai para teste
        assert metricas["recuperabilidade"]["n_teste"] == pytest.approx(
            len(com_divida) * 0.25, rel=0.02)


class TestInterpretabilidade:
    """Base do direito a explicacao (LGPD Art. 20)."""

    @pytest.fixture(scope="class")
    def importancia(self, ambiente_treinado):
        return modelo.importancia_atributos(ambiente_treinado["base"],
                                            "recuperabilidade", n_amostra=500)

    def test_importancia_cobre_todos_os_atributos(self, importancia):
        atributos = set(modelo.ATRIBUTOS_CATEGORICOS + modelo.ATRIBUTOS_NUMERICOS)
        assert set(importancia["atributo"]) == atributos

    def test_importancia_vem_ordenada(self, importancia):
        assert importancia["importancia"].is_monotonic_decreasing


class TestMontagemDaRequisicao:

    def test_parametros_da_listagem(self):
        corpo = {"order": {}, "limit": "0, 1000", "acao": "sgreceitas/listar"}
        assert json.dumps({"k1": corpo})  # serializa sem erro

    def test_cabecalho_disfarca_de_navegador(self):
        """O WAF do portal devolve 403 para User-Agent de biblioteca."""
        cabecalhos = coleta._cabecalhos()
        assert "Chrome" in cabecalhos["User-Agent"]
        assert "python" not in cabecalhos["User-Agent"].lower()
        assert cabecalhos["X-Requested-With"] == "XMLHttpRequest"

    def test_pausa_entre_requisicoes_configurada(self):
        """Secao 11 do plano de ensino: carga razoavel no servidor."""
        assert config.PAUSA_REQUISICAO > 0


class RespostaFalsa:
    """Duble minimo de resposta HTTP."""

    def __init__(self, carga, status=200):
        self._carga = carga
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._carga


class SessaoFalsa:
    """Sessao que devolve respostas programadas e conta as chamadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def post(self, *_args, **_kwargs):
        self.chamadas += 1
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


class TestChamadaDaApi:

    def test_extrai_a_lista_de_dados(self):
        sessao = SessaoFalsa([RespostaFalsa({"k1": {"total": 2, "dados": [{"a": 1}, {"a": 2}]}})])
        assert coleta.chamar_api(sessao, {}) == [{"a": 1}, {"a": 2}]

    def test_resposta_vazia_devolve_lista_vazia(self):
        sessao = SessaoFalsa([RespostaFalsa({"k1": {"total": 0, "dados": []}})])
        assert coleta.chamar_api(sessao, {}) == []

    def test_acao_inexistente_vira_erro(self):
        """A API devolve a string 'Acao nao encontrada' em vez de um objeto."""
        sessao = SessaoFalsa([RespostaFalsa({"k1": "Acao nao encontrada"})] * config.MAX_TENTATIVAS)
        with pytest.raises(ValueError):
            coleta.chamar_api(sessao, {})

    def test_retry_apos_falha_temporaria(self, monkeypatch):
        monkeypatch.setattr(coleta.time, "sleep", lambda _s: None)
        sessao = SessaoFalsa([
            requests.exceptions.ConnectTimeout("timeout"),
            RespostaFalsa({"k1": {"dados": [{"a": 1}]}}),
        ])
        assert coleta.chamar_api(sessao, {}) == [{"a": 1}]
        assert sessao.chamadas == 2

    def test_desiste_apos_o_limite_de_tentativas(self, monkeypatch):
        monkeypatch.setattr(coleta.time, "sleep", lambda _s: None)
        sessao = SessaoFalsa([requests.exceptions.ConnectTimeout("timeout")]
                             * config.MAX_TENTATIVAS)
        with pytest.raises(requests.exceptions.ConnectTimeout):
            coleta.chamar_api(sessao, {})
        assert sessao.chamadas == config.MAX_TENTATIVAS


class TestPaginacao:

    def test_para_quando_a_pagina_vem_incompleta(self, monkeypatch):
        """Pagina com menos de 1000 registros e a ultima."""
        monkeypatch.setattr(coleta.time, "sleep", lambda _s: None)
        monkeypatch.setattr(coleta, "abrir_sessao", lambda: None)

        paginas = [[{"id": i} for i in range(1000)], [{"id": 1000}]]
        monkeypatch.setattr(coleta, "chamar_api", lambda _s, _p: paginas.pop(0))

        resultado = coleta.baixar_arrecadacao()
        assert len(resultado) == 1001
        assert paginas == []

    def test_para_em_pagina_vazia(self, monkeypatch):
        monkeypatch.setattr(coleta.time, "sleep", lambda _s: None)
        monkeypatch.setattr(coleta, "abrir_sessao", lambda: None)
        monkeypatch.setattr(coleta, "chamar_api", lambda _s, _p: [])

        assert coleta.baixar_arrecadacao().empty

    def test_respeita_o_limite_de_paginas(self, monkeypatch):
        monkeypatch.setattr(coleta.time, "sleep", lambda _s: None)
        monkeypatch.setattr(coleta, "abrir_sessao", lambda: None)
        monkeypatch.setattr(coleta, "chamar_api",
                            lambda _s, _p: [{"id": i} for i in range(1000)])

        resultado = coleta.baixar_arrecadacao(limite_paginas=2)
        assert len(resultado) == 2000
