#!/usr/bin/env python3
"""Gera os sites estaticos do PoC para o GitHub Pages.

    python site/gerar_site.py

Produz DUAS publicacoes a partir do mesmo trabalho, para publicos diferentes:

  1. Academica (raiz do site) -- estudantes e banca do Projeto Integrador.
     Documentacao tecnica, Model Card, RIA, relatorio de EDA e links para o
     codigo-fonte no GitHub.

  2. Institucional (/sefin/) -- gestores da Secretaria Municipal de Fazenda.
     Linguagem de gestao publica, sem codigo, sem jargao academico e SEM
     QUALQUER LINK PARA O REPOSITORIO. Um gestor nao precisa ler Python para
     decidir sobre um piloto; oferecer isso na navegacao so distrai.

A separacao e por publico, nao por sigilo: as duas versoes descrevem o mesmo
sistema com os mesmos numeros. O que muda e o recorte e o vocabulario.

Saida em site/_saida/, publicada pelo workflow pages.yml.

Os sites sao ESTATICOS: o painel interativo nao roda neles, porque depende de um
servidor Python. As paginas iniciais explicam isso.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

import markdown


def slug_github(texto: str, separador: str) -> str:
    """Gera identificadores de cabecalho no mesmo esquema do GitHub.

    O padrao do Python-Markdown remove acentos e colapsa espacos, enquanto o
    GitHub preserva acentos e mantem um separador por espaco. A diferenca
    quebra as ancoras dos documentos: um sumario escrito para funcionar no
    GitHub aponta para ids que o site nao tem.

    Como os mesmos arquivos .md sao lidos no repositorio e publicados aqui,
    alinhamos o site ao GitHub -- e nao o contrario.

        "API antiga — o histórico"  ->  "api-antiga--o-histórico"

    (dois separadores porque o travessao sai e deixa os dois espacos.)
    """
    texto = unicodedata.normalize("NFC", texto).lower()
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE)
    return re.sub(r"\s", separador, texto)

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "site"
SAIDA = FONTE / "_saida"

REPOSITORIO = "https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas"

DESCRICAO_PADRAO = ("Prova de conceito do Projeto Integrador do Eixo II (UFT): predição de "
                    "inadimplência e priorização da dívida ativa de Palmas-TO, com auditoria "
                    "de justiça algorítmica.")

# --------------------------------------------------------------------------
# Definicao das duas publicacoes
# --------------------------------------------------------------------------
# paginas: (origem, destino, titulo, rotulo no menu)
PUBLICACOES = {
    "academica": {
        "diretorio": "",                       # raiz do site
        "marca": "Inteligência Tributária · Palmas-TO",
        "com_github": True,
        "com_notebook": True,
        "paginas": [
            (FONTE / "index.md", "index.html",
             "Inteligência Tributária de Palmas-TO", "Início"),
            (RAIZ / "docs" / "MANUAL_COLETA.md", "manual-coleta.html",
             "Manual de coleta de dados da Prefeitura de Palmas", "Coleta"),
            (RAIZ / "docs" / "AULA_SPRINT4_E3.md", "aula-sprint4-e3.html",
             "Aula — Sprint 4, E3: notebook e modelo serializado", "Aula Sprint 4"),
            (RAIZ / "docs" / "MODEL_CARD.md", "model-card.html",
             "Model Card", "Model Card"),
            (RAIZ / "docs" / "RIA.md", "ria.html",
             "Relatório de Impacto Algorítmico", "RIA"),
        ],
        "menu_extra": [("eda.html", "EDA")],
        "rodape": (
            "<p>Prova de conceito acadêmica do Projeto Integrador do Eixo II — "
            "Bacharelado Interdisciplinar em Inteligência Artificial, Universidade "
            "Federal do Tocantins. Coordenação: Prof. Dr. David Nadler Prata.</p>"
            "<p>Os números apresentados demonstram o funcionamento do sistema sobre uma "
            "carteira sintética calibrada — não descrevem a situação fiscal real do "
            f'município. <a href="{REPOSITORIO}">Código-fonte no GitHub</a>.</p>'
        ),
    },
    "sefin": {
        "diretorio": "sefin",
        "marca": "Inteligência Tributária",
        "com_github": False,                   # nenhum link para o repositorio
        "com_notebook": False,
        "paginas": [
            (FONTE / "sefin" / "index.md", "index.html",
             "Inteligência Tributária aplicada à dívida ativa", "Visão geral"),
            (FONTE / "sefin" / "como-funciona.md", "como-funciona.html",
             "Como funciona", "Como funciona"),
            (FONTE / "sefin" / "salvaguardas.md", "salvaguardas.html",
             "Salvaguardas e conformidade", "Salvaguardas"),
            (FONTE / "sefin" / "implantacao.md", "implantacao.html",
             "Roteiro de implantação", "Implantação"),
        ],
        "menu_extra": [],
        "rodape": (
            "<p>Prova de conceito desenvolvida pela Universidade Federal do Tocantins — "
            "Bacharelado Interdisciplinar em Inteligência Artificial. "
            "Coordenação: Prof. Dr. David Nadler Prata.</p>"
            "<p>Os percentuais apresentados resultam de simulação calibrada por dados "
            "públicos de arrecadação e não constituem projeção de receita. Estimativas "
            "com dados reais dependem de convênio para acesso ao cadastro.</p>"
        ),
    },
}

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
    <a class="nav-marca" href="index.html">{marca}</a>
    {menu}
  </div>
</nav>
<main>
{conteudo}
</main>
<footer class="rodape">
  <div class="rodape-conteudo">
{rodape}
  </div>
</footer>
</body>
</html>
"""


def montar_menu(publicacao: dict, pagina_atual: str) -> str:
    """Monta os links de navegacao, marcando a pagina corrente."""
    itens = [(destino, rotulo) for _, destino, _, rotulo in publicacao["paginas"]]
    itens += publicacao["menu_extra"]

    partes = []
    for destino, rotulo in itens:
        classe = ' class="ativo"' if destino == pagina_atual else ""
        partes.append(f'<a href="{destino}"{classe}>{rotulo}</a>')

    if publicacao["com_github"]:
        partes.append(f'<a href="{REPOSITORIO}">GitHub</a>')

    return "\n    ".join(partes)


def ajustar_ligacoes(html: str, com_github: bool) -> str:
    """Reescreve os links relativos do repositorio para o contexto do site.

    Nos arquivos Markdown os links apontam para caminhos do repositorio
    (`docs/RIA.md`, `src/modelo.py`). No site, os documentos viram paginas e o
    codigo-fonte passa a apontar para o GitHub -- exceto na publicacao
    institucional, onde esses links sao removidos e resta apenas o texto.
    """
    substituicoes = {
        r'href="docs/RIA\.md([^"]*)"': r'href="ria.html\1"',
        r'href="docs/MODEL_CARD\.md([^"]*)"': r'href="model-card.html\1"',
        r'href="RIA\.md([^"]*)"': r'href="ria.html\1"',
        r'href="MODEL_CARD\.md([^"]*)"': r'href="model-card.html\1"',
    }
    for padrao, troca in substituicoes.items():
        html = re.sub(padrao, troca, html)

    padrao_codigo = r'<a href="(?:src|app|tests|notebooks|\.github)/[^"]+">([^<]*)</a>'

    if com_github:
        def para_github(correspondencia: re.Match) -> str:
            return f'href="{REPOSITORIO}/blob/main/{correspondencia.group(1)}"'

        html = re.sub(r'href="((?:src|app|tests|notebooks|\.github)/[^"]+)"',
                      para_github, html)
    else:
        # Publicacao institucional: o link some, o texto permanece.
        html = re.sub(padrao_codigo, r"\1", html)

    return html


def marcar_caixas(html: str) -> str:
    """Transforma itens "[ ] texto" em caixas de selecao de verdade.

    O Python-Markdown nao conhece a sintaxe de lista de tarefas do GitHub e
    deixaria os colchetes como texto. As caixas ficam habilitadas: o aluno pode
    ir marcando o checklist na propria pagina.
    """
    html = re.sub(r"<li>\s*(?:<p>)?\[ \]\s*",
                  '<li class="tarefa"><input type="checkbox" aria-label="concluído"> ', html)
    html = re.sub(r"<li>\s*(?:<p>)?\[[xX]\]\s*",
                  '<li class="tarefa"><input type="checkbox" checked aria-label="concluído"> ',
                  html)
    return re.sub(r'<ul>(\s*<li class="tarefa">)', r'<ul class="tarefas">\1', html)


def montar_sumario(itens: list[dict]) -> str:
    """Sumario com as secoes de segundo nivel, para paginas longas."""
    secoes = [filho for item in itens for filho in item.get("children", [])
              if filho["level"] == 2]
    # So documentos longos ganham sumario: nas paginas de entrada ele seria ruido.
    if len(secoes) < 9 or any(s["name"].lower().startswith("sumário") for s in secoes):
        return ""        # pagina curta, ou o documento ja traz o proprio sumario
    linhas = "\n".join(f'<li><a href="#{s["id"]}">{s["name"]}</a></li>' for s in secoes)
    return ('<nav class="sumario" aria-label="Sumário"><p>Nesta página</p>'
            f"<ol>\n{linhas}\n</ol></nav>\n")


def converter_markdown(caminho: Path, com_github: bool) -> tuple[str, str]:
    """Converte um arquivo Markdown em HTML e devolve (html, descricao)."""
    texto = caminho.read_text(encoding="utf-8")

    conversor = markdown.Markdown(extensions=[
        "extra",          # tabelas, listas de definicao, blocos aninhados
        "sane_lists",
        "toc",
        "attr_list",
        "md_in_html",     # permite Markdown dentro das divs das paginas
        "codehilite",     # realce de sintaxe gerado aqui, sem JavaScript
    ], extension_configs={
        "toc": {"permalink": False, "slugify": slug_github},
        "codehilite": {"guess_lang": False, "css_class": "codigo"},
    })

    html = conversor.convert(texto)
    html = ajustar_ligacoes(html, com_github)
    html = marcar_caixas(html)

    # Tabelas largas precisam rolar sozinhas, sem empurrar a pagina.
    html = html.replace("<table>", '<div class="tabela-rolavel"><table>')
    html = html.replace("</table>", "</table></div>")

    # Sumario logo antes da primeira secao.
    sumario = montar_sumario(conversor.toc_tokens)
    if sumario and "<h2" in html:
        posicao = html.index("<h2")
        html = html[:posicao] + sumario + html[posicao:]

    # Primeiro paragrafo de texto vira a descricao da pagina.
    limpo = re.sub(r"<[^>]+>", "", html)
    linhas = [ln.strip() for ln in limpo.split("\n") if len(ln.strip()) > 60]
    descricao = (linhas[0][:180] if linhas else DESCRICAO_PADRAO).replace('"', "'")

    return html, descricao


def css_do_realce() -> str:
    """Folha de estilo do realce de sintaxe, nos modos claro e escuro."""
    from pygments.formatters import HtmlFormatter

    claro = HtmlFormatter(style="friendly", nobackground=True).get_style_defs(".codigo")
    escuro = HtmlFormatter(style="monokai", nobackground=True).get_style_defs(".codigo")
    return ("\n/* ---- Realce de sintaxe (gerado pelo Pygments) ---- */\n"
            f"{claro}\n"
            "@media (prefers-color-scheme: dark) {\n"
            f"{escuro}\n"
            "}\n")


def escrever_pagina(destino_dir: Path, publicacao: dict, destino: str,
                    titulo: str, conteudo: str, descricao: str) -> None:
    pagina = MODELO.format(titulo=titulo, descricao=descricao,
                           marca=publicacao["marca"],
                           menu=montar_menu(publicacao, destino),
                           conteudo=conteudo, rodape=publicacao["rodape"])
    (destino_dir / destino).write_text(pagina, encoding="utf-8")
    print(f"  {(destino_dir / destino).relative_to(SAIDA)}")


def gerar_notebook(destino_dir: Path, publicacao: dict) -> bool:
    """Converte o notebook de EDA em pagina do site."""
    caminho = RAIZ / "notebooks" / "eda_sprint2.ipynb"
    if not caminho.exists():
        print("  ! notebook nao encontrado; pagina de EDA nao sera gerada")
        return False

    try:
        import nbformat
        from nbconvert import HTMLExporter
    except ImportError:
        print("  ! nbconvert indisponivel; pagina de EDA nao sera gerada")
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

    escrever_pagina(destino_dir, publicacao, "eda.html", "Relatório de EDA — Sprint 2",
                    cabecalho + f'<div class="notebook-embutido">{corpo}</div>',
                    "Análise exploratória dos dados de arrecadação de Palmas-TO: hierarquia "
                    "de receitas, sazonalidade e perfil da dívida ativa.")
    return True


def gerar_publicacao(nome: str, publicacao: dict) -> int:
    destino_dir = SAIDA / publicacao["diretorio"] if publicacao["diretorio"] else SAIDA
    destino_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[{nome}]")
    for origem, destino, titulo, _ in publicacao["paginas"]:
        if not origem.exists():
            print(f"  ! ausente: {origem.name}")
            continue
        html, descricao = converter_markdown(origem, publicacao["com_github"])
        escrever_pagina(destino_dir, publicacao, destino, titulo, html, descricao)

    if publicacao["com_notebook"]:
        gerar_notebook(destino_dir, publicacao)

    estilo = (FONTE / "estilo.css").read_text(encoding="utf-8") + css_do_realce()
    (destino_dir / "estilo.css").write_text(estilo, encoding="utf-8")
    print(f"  {(destino_dir / 'estilo.css').relative_to(SAIDA)}")

    return len(list(destino_dir.glob("*.html")))


def main() -> int:
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True)

    print("Gerando os sites...")

    total = 0
    for nome, publicacao in PUBLICACOES.items():
        total += gerar_publicacao(nome, publicacao)

    # Impede o Jekyll de reprocessar a saida no GitHub Pages.
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")

    print(f"\nPronto: {total} páginas em {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
