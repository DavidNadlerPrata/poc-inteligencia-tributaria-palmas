#!/usr/bin/env python3
"""Gera o site estatico do PoC para o GitHub Pages.

    python site/gerar_site.py

Converte os documentos Markdown do projeto em HTML com um template comum e
transforma o notebook de EDA em pagina navegavel. A saida vai para site/_saida/,
que o workflow de Pages publica.

O site e ESTATICO: o painel Streamlit nao roda aqui, porque depende de um
servidor Python. A pagina inicial explica isso e ensina a rodar localmente.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import markdown

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "site"
SAIDA = FONTE / "_saida"

REPOSITORIO = "https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas"

# (arquivo de origem, pagina de destino, titulo, rotulo no menu)
PAGINAS = [
    (FONTE / "index.md", "index.html", "Inteligência Tributária de Palmas-TO", "Início"),
    (RAIZ / "docs" / "MODEL_CARD.md", "model-card.html", "Model Card", "Model Card"),
    (RAIZ / "docs" / "RIA.md", "ria.html", "Relatório de Impacto Algorítmico", "RIA"),
]

MENU_EXTRA = [("eda.html", "Relatório de EDA")]

MODELO = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descricao}">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{descricao}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="estilo.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='13' font-size='14'>&#x1F4CA;</text></svg>">
</head>
<body>
<nav class="nav">
  <div class="nav-conteudo">
    <a class="nav-marca" href="index.html">Inteligência Tributária · Palmas-TO</a>
    {menu}
    <a href="{repo}">GitHub</a>
  </div>
</nav>
<main>
{conteudo}
</main>
<footer class="rodape">
  <div class="rodape-conteudo">
    <p>Prova de conceito acadêmica do Projeto Integrador do Eixo II —
    Bacharelado Interdisciplinar em Inteligência Artificial, Universidade
    Federal do Tocantins. Coordenação: Prof. Dr. David Nadler Prata.</p>
    <p>Os números apresentados demonstram o funcionamento do sistema sobre uma
    carteira sintética calibrada — não descrevem a situação fiscal real do
    município. <a href="{repo}">Código-fonte no GitHub</a>.</p>
  </div>
</footer>
</body>
</html>
"""

DESCRICAO_PADRAO = ("Prova de conceito do Projeto Integrador do Eixo II (UFT): predição de "
                    "inadimplência e priorização da dívida ativa de Palmas-TO, com auditoria "
                    "de justiça algorítmica.")


def montar_menu(pagina_atual: str) -> str:
    """Monta os links de navegacao, marcando a pagina corrente."""
    itens = [(destino, rotulo) for _, destino, _, rotulo in PAGINAS] + MENU_EXTRA
    partes = []
    for destino, rotulo in itens:
        classe = ' class="ativo"' if destino == pagina_atual else ""
        partes.append(f'<a href="{destino}"{classe}>{rotulo}</a>')
    return "\n    ".join(partes)


def ajustar_ligacoes(html: str) -> str:
    """Reescreve os links relativos do repositorio para o contexto do site.

    Nos arquivos Markdown os links apontam para caminhos do repositorio
    (`docs/RIA.md`, `src/modelo.py`). No site, os documentos viram paginas e o
    codigo-fonte passa a apontar para o GitHub.
    """
    substituicoes = {
        r'href="docs/RIA\.md([^"]*)"': r'href="ria.html\1"',
        r'href="docs/MODEL_CARD\.md([^"]*)"': r'href="model-card.html\1"',
        r'href="RIA\.md([^"]*)"': r'href="ria.html\1"',
        r'href="MODEL_CARD\.md([^"]*)"': r'href="model-card.html\1"',
    }
    for padrao, troca in substituicoes.items():
        html = re.sub(padrao, troca, html)

    # Caminhos de codigo e diretorios do repositorio -> GitHub.
    def para_github(correspondencia: re.Match) -> str:
        caminho = correspondencia.group(1)
        return f'href="{REPOSITORIO}/blob/main/{caminho}"'

    html = re.sub(r'href="((?:src|app|tests|notebooks|\.github)/[^"]+)"', para_github, html)
    return html


def converter_markdown(caminho: Path) -> tuple[str, str]:
    """Converte um arquivo Markdown em HTML e devolve (html, primeiro paragrafo)."""
    texto = caminho.read_text(encoding="utf-8")

    conversor = markdown.Markdown(extensions=[
        "extra",          # tabelas, listas de definicao, blocos aninhados
        "sane_lists",
        "toc",
        "attr_list",
        "md_in_html",     # permite Markdown dentro das divs do index
    ], extension_configs={"toc": {"permalink": False}})

    html = conversor.convert(texto)
    html = ajustar_ligacoes(html)

    # Tabelas largas precisam rolar sozinhas, sem empurrar a pagina.
    html = html.replace("<table>", '<div class="tabela-rolavel"><table>')
    html = html.replace("</table>", "</table></div>")

    # Primeiro paragrafo de texto vira a descricao da pagina.
    limpo = re.sub(r"<[^>]+>", "", html)
    linhas = [ln.strip() for ln in limpo.split("\n") if len(ln.strip()) > 60]
    descricao = (linhas[0][:180] if linhas else DESCRICAO_PADRAO).replace('"', "'")

    return html, descricao


def escrever_pagina(destino: str, titulo: str, conteudo: str, descricao: str) -> None:
    pagina = MODELO.format(titulo=titulo, descricao=descricao, menu=montar_menu(destino),
                           conteudo=conteudo, repo=REPOSITORIO)
    (SAIDA / destino).write_text(pagina, encoding="utf-8")
    print(f"  {destino}")


def gerar_notebook() -> bool:
    """Converte o notebook de EDA em pagina do site."""
    caminho = RAIZ / "notebooks" / "eda_sprint2.ipynb"
    if not caminho.exists():
        print("  ! notebook nao encontrado; pagina de EDA sera um aviso")
        return False

    try:
        import nbformat
        from nbconvert import HTMLExporter
    except ImportError:
        print("  ! nbconvert indisponivel; pagina de EDA sera um aviso")
        return False

    caderno = nbformat.read(caminho, as_version=4)
    exportador = HTMLExporter(template_name="basic")   # so o corpo, sem <head>
    corpo, _ = exportador.from_notebook_node(caderno)

    cabecalho = (
        "<h1>Relatório de Análise Exploratória</h1>"
        '<p class="subtitulo">Sprint 2 — Coleta e ETL (Módulo 5). Notebook executado '
        "sobre os dados reais coletados da API da Prefeitura.</p>"
        f'<p class="creditos">Fonte executável: '
        f'<a href="{REPOSITORIO}/blob/main/notebooks/eda_sprint2.ipynb">'
        "notebooks/eda_sprint2.ipynb</a></p>"
    )

    escrever_pagina("eda.html", "Relatório de EDA — Sprint 2",
                    cabecalho + f'<div class="notebook-embutido">{corpo}</div>',
                    "Análise exploratória dos dados de arrecadação de Palmas-TO: hierarquia "
                    "de receitas, sazonalidade e perfil da dívida ativa.")
    return True


def main() -> int:
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True)

    print("Gerando o site...")

    for origem, destino, titulo, _ in PAGINAS:
        if not origem.exists():
            print(f"  ! ausente: {origem.name}")
            continue
        html, descricao = converter_markdown(origem)
        escrever_pagina(destino, titulo, html, descricao)

    gerar_notebook()

    shutil.copy2(FONTE / "estilo.css", SAIDA / "estilo.css")
    print("  estilo.css")

    # Impede o Jekyll de reprocessar a saida no GitHub Pages.
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")

    paginas = sorted(p.name for p in SAIDA.glob("*.html"))
    print(f"\nPronto: {len(paginas)} páginas em {SAIDA.relative_to(RAIZ)}")
    for nome in paginas:
        print(f"  - {nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
