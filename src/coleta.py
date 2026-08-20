"""Coleta de dados reais de arrecadacao via API REST da Prefeitura de Palmas.

Demonstra a Sprint 2 (Coleta e ETL - Modulo 5): consumo de API publica com
paginacao, retry com backoff exponencial e respeito a carga do servidor.

Endpoint: POST https://acessoainformacao.palmas.to.gov.br/api
  form-urlencoded:
    multi_request = true
    params = {"k1": {"order": {}, "limit": "<offset>, <qtd>", "acao": "<acao>"}}

Acoes descobertas por inspecao do JavaScript do portal:
  sgreceitas/listar    -> arrecadacao por codigo/orgao/mes (~177 mil registros)
  sgreceitas/detalhes  -> movimentacao diaria de uma linha da listagem
                          (parametros: ano, mes, codigo, orgao)
"""

from __future__ import annotations

import json
import time

import pandas as pd
import requests

import config


def abrir_sessao() -> requests.Session:
    """Cria a sessao HTTP e visita a pagina do modulo para obter cookies."""
    sessao = requests.Session()
    try:
        sessao.get(config.PORTAL_REFERER,
                   headers={"User-Agent": config.USER_AGENT},
                   timeout=config.TIMEOUT)
    except requests.exceptions.RequestException as erro:
        print(f"  aviso: nao abri a pagina de referencia ({erro}); seguindo mesmo assim.")
    return sessao


def _cabecalhos() -> dict:
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": config.USER_AGENT,
        "Referer": config.PORTAL_REFERER,
        "Origin": config.PORTAL_BASE,
    }


def chamar_api(sessao: requests.Session, parametros: dict) -> list[dict]:
    """POST na API com retry e backoff exponencial. Retorna a lista de registros."""
    corpo = {"multi_request": "true", "params": json.dumps({"k1": parametros})}

    for tentativa in range(1, config.MAX_TENTATIVAS + 1):
        try:
            resposta = sessao.post(config.PORTAL_API, data=corpo,
                                   headers=_cabecalhos(), timeout=config.TIMEOUT)
            resposta.raise_for_status()
            bloco = resposta.json().get("k1")
            if not isinstance(bloco, dict):
                raise ValueError(f"resposta inesperada da API: {str(bloco)[:80]}")
            return bloco.get("dados") or []
        except (requests.exceptions.RequestException, ValueError) as erro:
            if tentativa == config.MAX_TENTATIVAS:
                raise
            espera = 3 * (2 ** (tentativa - 1))
            print(f"  ! {erro.__class__.__name__}: tentativa {tentativa}/"
                  f"{config.MAX_TENTATIVAS}, aguardando {espera}s")
            time.sleep(espera)
    return []


def baixar_arrecadacao(ano: str | None = None, mes: str | None = None,
                       limite_paginas: int | None = None) -> pd.DataFrame:
    """Baixa a listagem de arrecadacao, opcionalmente filtrada por ano/mes."""
    sessao = abrir_sessao()
    registros: list[dict] = []
    offset = 0
    pagina = 0

    while True:
        parametros = {"order": {}, "limit": f"{offset}, 1000", "acao": "sgreceitas/listar"}
        if ano:
            parametros["ano"] = ano
        if mes:
            parametros["mes"] = mes

        dados = chamar_api(sessao, parametros)
        if not dados:
            break

        registros.extend(dados)
        pagina += 1
        print(f"  pagina {pagina}: {len(registros)} registros acumulados")

        if len(dados) < 1000:
            break
        if limite_paginas and pagina >= limite_paginas:
            print("  (limite de paginas atingido)")
            break

        offset += 1000
        time.sleep(config.PAUSA_REQUISICAO)

    return pd.DataFrame(registros)


def baixar_movimentacao_diaria(sessao: requests.Session, linha: dict) -> list[dict]:
    """Baixa o detalhamento diario de uma linha da listagem de arrecadacao."""
    parametros = {
        "order": {}, "limit": "0, 1000", "acao": "sgreceitas/detalhes",
        "ano": linha["ano"], "mes": linha["mes"],
        "codigo": linha["codigo_original"], "orgao": linha["orgao"],
    }
    return chamar_api(sessao, parametros)


def coletar(ano: str = "2025", forcar: bool = False) -> pd.DataFrame:
    """Coleta a arrecadacao do ano, usando cache local quando disponivel."""
    if config.CSV_ARRECADACAO.exists() and not forcar:
        print(f"Usando cache: {config.CSV_ARRECADACAO.name}")
        return pd.read_csv(config.CSV_ARRECADACAO, sep=";", dtype=str)

    print(f"Coletando arrecadacao de {ano} na API da Prefeitura de Palmas...")
    df = baixar_arrecadacao(ano=ano)

    if df.empty:
        raise RuntimeError("A API nao retornou registros. Verifique conectividade e filtros.")

    df.to_csv(config.CSV_ARRECADACAO, sep=";", index=False, encoding="utf-8-sig")
    print(f"  {len(df)} registros salvos em {config.CSV_ARRECADACAO.name}")
    return df


if __name__ == "__main__":
    dados = coletar()
    print(dados.head())
