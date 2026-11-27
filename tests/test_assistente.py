"""Testes do laco do agente (src/assistente.py), sem rede e sem chave de API.

O modelo de linguagem e substituido por um roteiro: uma lista de respostas que
ele "daria". Assim da para testar exatamente o que o codigo faz com cada
resposta -- executar ferramentas, devolver erros, parar no limite de passos,
registrar a auditoria -- sem custo e sem depender de um servico externo.

O comportamento do modelo de verdade e avaliado a parte, com chave, por
avaliar_assistente.py.
"""

from __future__ import annotations

import copy
import json

import pytest
import requests

import assistente
import config


def _pedido(nome: str, argumentos, identificador: str = "chamada-1") -> dict:
    bruto = argumentos if isinstance(argumentos, str) else json.dumps(argumentos)
    return {"id": identificador, "type": "function",
            "function": {"name": nome, "arguments": bruto}}


def _passo(texto: str = "", pedidos: list | None = None, raciocinio=None, custo=0.0) -> dict:
    mensagem = {"role": "assistant", "content": texto}
    if pedidos:
        mensagem["tool_calls"] = pedidos
    if raciocinio:
        mensagem["reasoning_details"] = raciocinio
    return {"mensagem": mensagem, "motivo_parada": "tool_calls" if pedidos else "stop",
            "uso": {"prompt_tokens": 100, "completion_tokens": 20, "cost": custo},
            "provedor": "roteiro"}


class ClienteRoteirizado:
    """Faz as vezes do OpenRouter: devolve as respostas na ordem do roteiro."""

    modelo = "roteiro/teste"

    def __init__(self, roteiro: list[dict], repetir_ultimo: bool = False):
        self.roteiro = list(roteiro)
        self.repetir_ultimo = repetir_ultimo
        self.recebidas: list[list[dict]] = []

    def completar(self, mensagens, esquemas):
        self.recebidas.append(copy.deepcopy(mensagens))
        if self.repetir_ultimo and len(self.roteiro) == 1:
            return copy.deepcopy(self.roteiro[0])
        return self.roteiro.pop(0)


@pytest.fixture
def montar(ambiente_treinado, tmp_path):
    def _montar(roteiro, **opcoes):
        cliente = ClienteRoteirizado(roteiro, opcoes.pop("repetir_ultimo", False))
        agente = assistente.Assistente(cliente, arquivo_log=tmp_path / "auditoria.jsonl",
                                       **opcoes)
        return agente, cliente
    return _montar


def _log(tmp_path) -> list[dict]:
    linhas = (tmp_path / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas]


class TestLacoDoAgente:

    def test_resposta_direta_sem_ferramenta(self, montar):
        agente, cliente = montar([_passo("Posso ajudar com a carteira.")])
        resposta = agente.responder("Oi")
        assert resposta.texto == "Posso ajudar com a carteira."
        assert resposta.chamadas == []
        assert len(cliente.recebidas) == 1

    def test_executa_a_ferramenta_e_devolve_o_resultado_ao_modelo(self, montar):
        agente, cliente = montar([
            _passo(pedidos=[_pedido("fila_cobranca", {"limite": 2}, "id-abc")],
                   raciocinio=[{"type": "reasoning.text", "text": "preciso da fila"}]),
            _passo("Os dois primeiros sao..."),
        ])
        resposta = agente.responder("Quem lidera a fila?")

        segunda = cliente.recebidas[1]
        pedido_do_modelo = segunda[-2]
        assert pedido_do_modelo["role"] == "assistant"
        assert pedido_do_modelo["reasoning_details"] == [
            {"type": "reasoning.text", "text": "preciso da fila"}], "raciocinio deve voltar intacto"

        devolvido = segunda[-1]
        assert devolvido["role"] == "tool" and devolvido["tool_call_id"] == "id-abc"
        assert len(json.loads(devolvido["content"])["primeiros_casos"]) == 2

        assert resposta.texto == "Os dois primeiros sao..."
        assert resposta.chamadas[0]["ferramenta"] == "fila_cobranca"

    def test_varias_ferramentas_no_mesmo_passo(self, montar):
        agente, cliente = montar([
            _passo(pedidos=[_pedido("resumo_carteira", {}, "a"),
                            _pedido("desempenho_modelos", {}, "b")]),
            _passo("pronto"),
        ])
        agente.responder("Panorama e desempenho")
        devolvidos = [m for m in cliente.recebidas[1] if m["role"] == "tool"]
        assert [m["tool_call_id"] for m in devolvidos] == ["a", "b"]

    def test_ferramenta_inexistente_volta_como_erro_e_o_laco_segue(self, montar):
        agente, cliente = montar([
            _passo(pedidos=[_pedido("apagar_banco", {})]),
            _passo("Nao tenho essa ferramenta."),
        ])
        resposta = agente.responder("Apague tudo")
        assert "erro" in json.loads(cliente.recebidas[1][-1]["content"])
        assert resposta.texto == "Nao tenho essa ferramenta."

    def test_argumentos_que_nao_sao_json(self, montar):
        agente, cliente = montar([
            _passo(pedidos=[_pedido("fila_cobranca", "{limite: dois")]),
            _passo("Corrigi."),
        ])
        agente.responder("fila")
        assert "JSON" in json.loads(cliente.recebidas[1][-1]["content"])["erro"]

    def test_para_no_limite_de_passos(self, montar):
        agente, cliente = montar([_passo(pedidos=[_pedido("resumo_carteira", {})])],
                                 repetir_ultimo=True, max_passos=3)
        resposta = agente.responder("loop")
        assert len(cliente.recebidas) == 3
        assert "limite de consultas" in resposta.texto

    def test_texto_vazio_nao_quebra(self, montar):
        agente, _ = montar([_passo("")])
        assert agente.responder("?").texto == "(o modelo nao devolveu texto)"


class TestHistorico:

    def test_prompt_de_sistema_vai_uma_vez_e_nao_volta_no_historico(self, montar):
        agente, cliente = montar([_passo("primeira"), _passo("segunda")])
        primeira = agente.responder("pergunta 1")
        assert all(m["role"] != "system" for m in primeira.mensagens)

        agente.responder("pergunta 2", primeira.mensagens)
        enviadas = cliente.recebidas[1]
        assert [m["role"] for m in enviadas].count("system") == 1
        assert enviadas[0]["role"] == "system"
        assert [m["content"] for m in enviadas if m["role"] == "user"] == ["pergunta 1",
                                                                           "pergunta 2"]

    def test_resultado_de_ferramenta_fica_no_historico(self, montar):
        """A pergunta seguinte ('e o segundo?') depende do que a ferramenta devolveu antes."""
        agente, _ = montar([_passo(pedidos=[_pedido("fila_cobranca", {"limite": 1})]),
                            _passo("ok")])
        resposta = agente.responder("primeiro da fila")
        assert any(m["role"] == "tool" for m in resposta.mensagens)


class TestAuditoria:

    def test_cada_pergunta_gera_um_registro(self, montar, tmp_path):
        agente, _ = montar([
            _passo(pedidos=[_pedido("indicadores_por", {"dimensao": "setor_urbano"})], custo=0.001),
            _passo("Taquaralto lidera.", custo=0.002),
        ])
        agente.responder("Qual setor lidera?")
        [registro] = _log(tmp_path)
        assert registro["pergunta"] == "Qual setor lidera?"
        assert registro["resposta"] == "Taquaralto lidera."
        assert registro["ferramentas"] == [{"nome": "indicadores_por",
                                            "argumentos": {"dimensao": "setor_urbano"},
                                            "erro": None}]
        assert registro["uso"]["custo_usd"] == pytest.approx(0.003)
        assert registro["modelo"] == "roteiro/teste"

    def test_erro_de_ferramenta_fica_registrado(self, montar, tmp_path):
        agente, _ = montar([_passo(pedidos=[_pedido("fila_cobranca", {"limite": 999})]),
                            _passo("nao deu")])
        agente.responder("fila enorme")
        assert "entre" in _log(tmp_path)[0]["ferramentas"][0]["erro"]


class RespostaHttp:
    def __init__(self, status: int, corpo):
        self.status_code = status
        self._corpo = corpo

    def json(self):
        if isinstance(self._corpo, Exception):
            raise self._corpo
        return self._corpo


class SessaoFalsa:
    def __init__(self, respostas: list):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []

    def post(self, url, headers, json, timeout):
        self.chamadas.append({"url": url, "headers": headers, "json": json})
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


OK = RespostaHttp(200, {"choices": [{"message": {"role": "assistant", "content": "oi"},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0},
                        "provider": "X"})


class TestClienteOpenRouter:

    @pytest.fixture(autouse=True)
    def sem_espera(self, monkeypatch):
        monkeypatch.setattr(assistente.time, "sleep", lambda _: None)

    def test_corpo_da_requisicao(self):
        sessao = SessaoFalsa([OK])
        cliente = assistente.ClienteOpenRouter("chave-teste", "modelo/x", sessao=sessao)
        retorno = cliente.completar([{"role": "user", "content": "oi"}], [{"type": "function"}])

        enviado = sessao.chamadas[0]
        assert enviado["url"] == assistente.URL_OPENROUTER
        assert enviado["headers"]["Authorization"] == "Bearer chave-teste"
        assert enviado["json"]["model"] == "modelo/x"
        assert enviado["json"]["tools"] == [{"type": "function"}]
        assert enviado["json"]["reasoning"] == {"enabled": True}
        assert enviado["json"]["provider"] == {"data_collection": "deny"}
        assert retorno["mensagem"]["content"] == "oi"

    def test_repete_em_erro_transitorio(self):
        sessao = SessaoFalsa([RespostaHttp(429, {"error": {"message": "calma"}}), OK])
        retorno = assistente.ClienteOpenRouter("k", sessao=sessao).completar([], [])
        assert retorno["mensagem"]["content"] == "oi"
        assert len(sessao.chamadas) == 2

    def test_repete_em_falha_de_rede(self):
        sessao = SessaoFalsa([requests.ConnectionError("caiu"), OK])
        assistente.ClienteOpenRouter("k", sessao=sessao).completar([], [])
        assert len(sessao.chamadas) == 2

    def test_chave_invalida_nao_repete(self):
        sessao = SessaoFalsa([RespostaHttp(401, {"error": {"message": "chave invalida"}})])
        with pytest.raises(assistente.ErroAssistente, match="401"):
            assistente.ClienteOpenRouter("k", sessao=sessao).completar([], [])
        assert len(sessao.chamadas) == 1

    def test_erro_no_corpo_de_resposta_200(self):
        sessao = SessaoFalsa([RespostaHttp(200, {"error": {"message": "modelo indisponivel"}})])
        with pytest.raises(assistente.ErroAssistente, match="indisponivel"):
            assistente.ClienteOpenRouter("k", sessao=sessao).completar([], [])

    def test_corpo_que_nao_e_json(self):
        sessao = SessaoFalsa([RespostaHttp(502, ValueError("html"))] * 3)
        with pytest.raises(assistente.ErroAssistente, match="502"):
            assistente.ClienteOpenRouter("k", sessao=sessao).completar([], [])


class TestConfiguracao:

    @pytest.fixture
    def sem_chave(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        monkeypatch.setattr(config, "RAIZ", tmp_path)
        return tmp_path

    def test_sem_chave_a_mensagem_orienta(self, sem_chave):
        with pytest.raises(assistente.ErroAssistente, match="OPENROUTER_API_KEY"):
            assistente.ler_configuracao()

    def test_le_do_arquivo_env(self, sem_chave):
        (sem_chave / ".env").write_text('# comentario\nOPENROUTER_API_KEY="do-arquivo"\n',
                                        encoding="utf-8")
        assert assistente.ler_configuracao() == ("do-arquivo", assistente.MODELO_PADRAO)

    def test_ambiente_vence_o_arquivo(self, sem_chave, monkeypatch):
        (sem_chave / ".env").write_text("OPENROUTER_API_KEY=do-arquivo\n", encoding="utf-8")
        monkeypatch.setenv("OPENROUTER_API_KEY", "do-ambiente")
        monkeypatch.setenv("OPENROUTER_MODEL", "outro/modelo")
        assert assistente.ler_configuracao() == ("do-ambiente", "outro/modelo")

    def test_segredos_do_streamlit_vencem_tudo(self, sem_chave, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "do-ambiente")
        chave, _ = assistente.ler_configuracao({"OPENROUTER_API_KEY": "do-secrets"})
        assert chave == "do-secrets"
