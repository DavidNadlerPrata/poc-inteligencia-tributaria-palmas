"""Testes do material de aula da Sprint 4 (docs/AULA_SPRINT4_E3.md).

A primeira versao da aula foi publicada com codigo que nao executava em
sequencia, treinava com o grupo protegido e gravava um numero inteiro no lugar
do modelo. Nada disso gerava mensagem de erro para quem lia a pagina.

Estes testes fazem o que um aluno faria: copiam cada bloco python da aula, na
ordem, e executam. Rodam num projeto temporario, entao nao tocam em data/ nem
em models/ do repositorio.

Convencao: blocos que comecam com "# ERRADO" ou "# ARMADILHA" sao
contraexemplos e nao sao executados. Todo o resto precisa rodar.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import joblib
import pytest
from sklearn.pipeline import Pipeline

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "docs"))

import gerar_aula  # noqa: E402


@pytest.fixture(scope="module")
def trilha():
    """Executa a aula publicada uma vez e entrega o namespace resultante."""
    if not gerar_aula.CARTEIRA.exists():
        pytest.skip("carteira versionada ausente")
    texto = gerar_aula.FINAL.read_text(encoding="utf-8")
    namespace, raiz_tmp = gerar_aula.executar_trilha(texto)
    yield namespace, raiz_tmp
    shutil.rmtree(raiz_tmp, ignore_errors=True)


class TestDocumento:

    def test_nao_sobrou_marcador_sem_preencher(self):
        texto = gerar_aula.FINAL.read_text(encoding="utf-8")
        assert not gerar_aula.PADRAO_MARCADOR.findall(texto), (
            "ha marcadores no arquivo final; rode python docs/gerar_aula.py")

    def test_codigo_do_final_e_o_do_modelo(self):
        """Quem edita o arquivo final em vez do modelo perde a alteracao na
        proxima geracao -- e, ate la, publica numeros que nao vieram do codigo."""
        do_modelo = gerar_aula.extrair_blocos(gerar_aula.MODELO.read_text(encoding="utf-8"))
        do_final = gerar_aula.extrair_blocos(gerar_aula.FINAL.read_text(encoding="utf-8"))
        assert [c for _, c in do_modelo] == [c for _, c in do_final], (
            "o codigo divergiu; edite o .modelo.md e rode python docs/gerar_aula.py")

    def test_contraexemplos_estao_marcados(self):
        blocos = gerar_aula.extrair_blocos(gerar_aula.FINAL.read_text(encoding="utf-8"))
        contraexemplos = [c for _, c in blocos if gerar_aula.e_contraexemplo(c)]
        assert len(contraexemplos) >= 3
        assert len(blocos) - len(contraexemplos) >= 15


class TestTrilhaExecuta:

    def test_todos_os_blocos_rodam_em_sequencia(self, trilha):
        namespace, _ = trilha
        assert "modelo_inadimplencia" in namespace
        assert "modelo_recuperabilidade" in namespace

    def test_grupo_protegido_fora_de_tudo(self, trilha):
        """IPTU Social nao pode aparecer em nenhum conjunto que alimenta modelo."""
        namespace, _ = trilha
        for nome in ("universo", "treino", "teste", "treino_rec", "teste_rec"):
            assert namespace[nome]["iptu_social"].sum() == 0, (
                f"beneficiarios do IPTU Social presentes em '{nome}'")

    def test_a_carteira_tinha_beneficiarios_a_excluir(self, trilha):
        """Sem isto, o teste anterior passaria sem exercitar nada."""
        namespace, _ = trilha
        assert namespace["dados"]["iptu_social"].sum() > 0

    def test_split_e_temporal_e_sem_sobreposicao(self, trilha):
        namespace, _ = trilha
        treino, teste = namespace["treino"], namespace["teste"]
        assert treino["competencia"].max() < teste["competencia"].min()
        assert not set(treino["id_contribuinte"]) & set(teste["id_contribuinte"])

    def test_dados_ordenados_para_a_validacao_temporal(self, trilha):
        """TimeSeriesSplit divide por posicao: a ordem cronologica e obrigatoria."""
        namespace, _ = trilha
        assert namespace["treino"]["competencia"].is_monotonic_increasing

    def test_nenhuma_coluna_proibida_entre_os_atributos(self, trilha):
        namespace, _ = trilha
        atributos = set(namespace["ATRIBUTOS"])
        for coluna in ("inadimplente_proximo_exercicio", "divida_recuperada_12m",
                       "faixa_renda_setor", "iptu_social", "competencia", "id_contribuinte"):
            assert coluna not in atributos

    def test_modelo_2_so_ve_quem_tem_divida(self, trilha):
        namespace, _ = trilha
        assert (namespace["treino_rec"]["valor_divida_consolidada"] > 0).all()
        assert (namespace["teste_rec"]["valor_divida_consolidada"] > 0).all()

    def test_corte_e_uma_probabilidade(self, trilha):
        namespace, _ = trilha
        assert isinstance(namespace["CORTE"], float)
        assert 0.0 < namespace["CORTE"] < 1.0


class TestArtefatos:
    """O que a trilha deixa em disco e o que o E3 manda versionar."""

    @pytest.mark.parametrize("nome", ["modelo_inadimplencia", "modelo_recuperabilidade"])
    def test_arquivo_salvo_e_um_pipeline(self, trilha, nome):
        """Regressao direta do defeito original: o arquivo continha o inteiro 600."""
        _, raiz_tmp = trilha
        recarregado = joblib.load(raiz_tmp / "models" / f"{nome}.joblib")
        assert isinstance(recarregado, Pipeline)
        assert hasattr(recarregado, "predict_proba")

    @pytest.mark.parametrize("nome", ["modelo_inadimplencia", "modelo_recuperabilidade"])
    def test_metadados_acompanham_o_modelo(self, trilha, nome):
        _, raiz_tmp = trilha
        registro = json.loads((raiz_tmp / "models" / f"{nome}.json").read_text(encoding="utf-8"))
        assert registro["split"]["tipo"] == "temporal"
        assert registro["algoritmo"]
        assert set(registro["metricas_teste"]) >= {"acuracia", "precisao", "recall",
                                                   "f1", "roc_auc", "matriz_confusao"}

    def test_corte_registrado_nos_metadados(self, trilha):
        namespace, raiz_tmp = trilha
        registro = json.loads(
            (raiz_tmp / "models" / "modelo_inadimplencia.json").read_text(encoding="utf-8"))
        assert registro["corte_decisao"] == namespace["CORTE"]

    @pytest.mark.parametrize("arquivo", [
        "avaliacao_teste_inadimplencia.csv",
        "metricas_por_subgrupo_inadimplencia.csv",
        "avaliacao_teste_recuperabilidade.csv",
    ])
    def test_insumos_da_sprint_5_foram_salvos(self, trilha, arquivo):
        _, raiz_tmp = trilha
        assert (raiz_tmp / "data" / arquivo).stat().st_size > 0

    def test_modelos_cabem_no_github(self, trilha):
        """O GitHub recusa arquivos acima de 100 MB."""
        _, raiz_tmp = trilha
        for arquivo in (raiz_tmp / "models").glob("*.joblib"):
            assert arquivo.stat().st_size < 50 * 1024 * 1024


class TestResultadosPlausiveis:

    @pytest.mark.parametrize("chave", ["metricas_inadimplencia", "metricas_recuperabilidade"])
    def test_modelo_supera_o_acaso_sem_sinal_de_vazamento(self, trilha, chave):
        namespace, _ = trilha
        auc = namespace[chave]["roc_auc"]
        assert 0.55 < auc < 0.95, f"{chave}: ROC-AUC {auc:.3f} fora do plausivel"

    def test_faixas_de_recuperabilidade_em_ordem(self, trilha):
        """Faixa 'alta' precisa recuperar mais que 'media', e esta mais que 'baixa'."""
        namespace, _ = trilha
        observada = namespace["calibracao"]["taxa_observada"]
        assert observada["alta"] > observada["media"] > observada["baixa"]

    def test_fila_ordenada_por_retorno_esperado(self, trilha):
        namespace, _ = trilha
        assert namespace["fila"]["retorno_esperado"].is_monotonic_decreasing
