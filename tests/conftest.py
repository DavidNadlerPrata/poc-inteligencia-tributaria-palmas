"""Fixtures compartilhadas pela suite de testes.

Todos os testes rodam sobre um banco temporario e uma amostra reduzida da
carteira, para nao tocar nos artefatos gerados pelo pipeline real nem depender
de rede.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

import config  # noqa: E402
import etl  # noqa: E402
import modelo  # noqa: E402
import sintetico  # noqa: E402

TAMANHO_TESTE = 3_000


@pytest.fixture(scope="session")
def carteira():
    """Carteira pequena, gerada uma vez por sessao de teste."""
    return sintetico.gerar_carteira(n=TAMANHO_TESTE, semente=config.SEMENTE)


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    """Redireciona o banco e o diretorio de dados para uma pasta temporaria."""
    caminho = tmp_path / "teste.db"
    monkeypatch.setattr(config, "BANCO", caminho)
    monkeypatch.setattr(config, "DADOS", tmp_path)
    return caminho


@pytest.fixture
def base_analitica(carteira, banco_temporario):
    """Visao analitica carregada de um banco recem-construido."""
    etl.executar(carteira)
    return etl.carregar_visao_analitica()


@pytest.fixture(scope="session")
def ambiente_treinado(carteira, tmp_path_factory):
    """Banco montado e modelos treinados uma unica vez para toda a suite.

    Treinar e a operacao mais cara da suite; repeti-la por teste tornaria a
    execucao lenta o bastante para desestimular rodar os testes -- que e como
    uma suite morre. Os artefatos ficam em diretorio temporario, isolados dos
    arquivos do pipeline real.
    """
    diretorio = tmp_path_factory.mktemp("ambiente_treinado")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "BANCO", diretorio / "teste.db")
        patch.setattr(config, "DADOS", diretorio)
        patch.setattr(config, "MODELOS", diretorio)
        patch.setattr(config, "MODELO_INADIMPLENCIA", diretorio / "inadimplencia.joblib")
        patch.setattr(config, "MODELO_RECUPERABILIDADE", diretorio / "recuperabilidade.joblib")
        patch.setattr(config, "METRICAS", diretorio / "metricas.json")

        etl.executar(carteira)
        base = etl.carregar_visao_analitica()
        metricas = modelo.treinar(base)

        yield {"base": base, "metricas": metricas, "diretorio": diretorio}


@pytest.fixture(scope="session")
def base_treinada(ambiente_treinado):
    """Visao analitica correspondente aos modelos ja treinados."""
    return ambiente_treinado["base"]


@pytest.fixture(scope="session")
def metricas_treino(ambiente_treinado):
    """Metricas devolvidas pelo treino."""
    return ambiente_treinado["metricas"]


@pytest.fixture(scope="session")
def fila_cobranca(ambiente_treinado):
    """Fila priorizada, gerada com os modelos da sessao."""
    return modelo.priorizar_cobranca(ambiente_treinado["base"])
