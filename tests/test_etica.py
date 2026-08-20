"""Testes das regras eticas nao negociaveis do sistema.

Este e o arquivo mais importante da suite. As regras aqui verificadas nao sao
preferencias de projeto: sao compromissos declarados no Model Card e no RIA.

O Model Card afirma que a exclusao do IPTU Social deve ser "verificada por teste
automatizado, nao por disciplina de quem opera". Este arquivo cumpre essa
promessa. Se qualquer teste daqui falhar, o sistema NAO pode ser usado --
independentemente de quao boas estejam as metricas de desempenho.
"""

from __future__ import annotations

import pandas as pd
import pytest

import modelo


class TestExclusaoIptuSocial:
    """Beneficiarios do IPTU Social ficam fora de toda acao preditiva.

    Base: secao 11 do plano de ensino e secao 2.4 do RIA. Sao idosos,
    aposentados, pensionistas e PCD de baixa renda, isentos por lei municipal.
    """

    def test_universo_de_treino_nao_contem_beneficiarios(self, base_analitica):
        universo = modelo._excluir_grupo_protegido(base_analitica)
        assert (universo["iptu_social"] == 0).all(), (
            "beneficiario do IPTU Social presente no universo de treino")

    def test_exclusao_remove_exatamente_os_beneficiarios(self, base_analitica):
        esperado = int((base_analitica["iptu_social"] == 0).sum())
        universo = modelo._excluir_grupo_protegido(base_analitica)
        assert len(universo) == esperado

    def test_carteira_de_teste_tem_beneficiarios_a_excluir(self, base_analitica):
        """Guarda contra um falso positivo: se nao houvesse beneficiario algum,
        os testes acima passariam sem exercitar nada."""
        assert base_analitica["iptu_social"].sum() > 0, (
            "a carteira de teste precisa conter beneficiarios do IPTU Social")

    def test_fila_de_cobranca_nao_contem_beneficiarios(self, fila_cobranca):
        assert (fila_cobranca["iptu_social"] == 0).all(), (
            "beneficiario do IPTU Social apareceu na fila de cobranca")


class TestGrupoProtegidoNaoEPreditor:
    """A faixa de renda do setor e usada so na auditoria, nunca como atributo.

    Decisao registrada na secao 3 do Model Card. Nao elimina o vies indireto,
    mas impede a discriminacao direta e explicita por renda.
    """

    def test_faixa_de_renda_fora_dos_atributos(self):
        atributos = modelo.ATRIBUTOS_CATEGORICOS + modelo.ATRIBUTOS_NUMERICOS
        assert modelo.COLUNA_PROTEGIDA not in atributos

    def test_alvos_fora_dos_atributos(self):
        """Alvo entre os preditores seria vazamento de dados."""
        atributos = set(modelo.ATRIBUTOS_CATEGORICOS + modelo.ATRIBUTOS_NUMERICOS)
        for alvo in ("inadimplente_proximo_exercicio", "divida_recuperada_12m"):
            assert alvo not in atributos, f"vazamento: {alvo} usado como preditor"

    def test_iptu_social_fora_dos_atributos(self):
        """Dado sensivel (LGPD Art. 5, II) so pode servir para excluir."""
        atributos = set(modelo.ATRIBUTOS_CATEGORICOS + modelo.ATRIBUTOS_NUMERICOS)
        assert "iptu_social" not in atributos


class TestPseudonimizacao:
    """Identificadores diretos nao circulam no pipeline (LGPD Art. 13)."""

    def test_identificador_e_hash_e_nao_reversivel(self, carteira):
        ids = carteira["id_contribuinte"]
        assert ids.str.fullmatch(r"[0-9a-f]{16}").all(), (
            "id_contribuinte deveria ser hash hexadecimal de 16 caracteres")

    def test_identificador_e_unico(self, carteira):
        assert carteira["id_contribuinte"].is_unique

    def test_carteira_nao_traz_identificadores_diretos(self, carteira):
        proibidos = {"cpf", "cnpj", "nome", "endereco", "email", "telefone",
                     "inscricao_imobiliaria"}
        presentes = proibidos & {c.lower() for c in carteira.columns}
        assert not presentes, f"identificador direto na carteira: {presentes}"


class TestPriorizacaoUsaModeloCorreto:
    """A fila e ordenada pelo Modelo 2, nunca pelo Modelo 1.

    Achado central do RIA: o modelo de inadimplencia reprova nos dois testes de
    fairness e por isso nao pode direcionar cobranca.
    """

    def test_fila_traz_probabilidade_de_recuperacao(self, fila_cobranca):
        assert "prob_recuperacao" in fila_cobranca.columns
        assert "prob_inadimplencia" not in fila_cobranca.columns

    def test_retorno_esperado_e_o_produto_declarado(self, fila_cobranca):
        """retorno_esperado = valor da divida x P(recuperacao), como diz o RIA."""
        esperado = (fila_cobranca["valor_divida_consolidada"]
                    * fila_cobranca["prob_recuperacao"])
        pd.testing.assert_series_equal(
            fila_cobranca["retorno_esperado"], esperado.round(2), check_names=False)

    def test_fila_ordenada_por_retorno_decrescente(self, fila_cobranca):
        assert fila_cobranca["retorno_esperado"].is_monotonic_decreasing

    def test_fila_so_contem_quem_tem_divida(self, fila_cobranca):
        assert (fila_cobranca["valor_divida_consolidada"] > 0).all()


@pytest.mark.parametrize("probabilidade,faixa", [
    (0.00, "baixa"), (0.32, "baixa"),
    (0.33, "media"), (0.50, "media"), (0.65, "media"),
    (0.66, "alta"), (1.00, "alta"),
])
def test_faixas_de_recuperabilidade_nas_fronteiras(probabilidade, faixa):
    """As faixas alta/media/baixa exigidas pelo plano de ensino, nos limites."""
    assert modelo.faixa_recuperabilidade(probabilidade) == faixa
