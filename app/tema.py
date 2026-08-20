"""Paleta e tema dos graficos do painel.

Os valores vem da paleta de referencia validada do guia de visualizacao.
Subconjuntos usados e sua situacao de validacao:

  * Categorico (2-3 series): slots 1-3 -- blue, orange, aqua. A paleta de
    referencia documenta esses tres slots como aprovados em TODOS os pares nos
    dois modos (pior par CVD dE 9,2 claro / 9,4 escuro; visao normal 24,0 / 20,9).
  * Ordinal de 3 passos (faixas alta/media/baixa): rampa azul de uma hue. No
    modo claro o passo mais claro nao pode ser mais claro que o 250 (#86b6ef),
    que garante contraste 2:1 com a superficie.

Regra seguida em todo o painel: texto usa tokens de tinta (primaria, secundaria,
muted), nunca a cor da serie. A cor fica nas marcas.
"""

from __future__ import annotations

# ----------------------------- Superficies e tinta -----------------------------
CLARO = {
    "superficie": "#fcfcfb",
    "plano": "#f9f9f7",
    "tinta_primaria": "#0b0b0b",
    "tinta_secundaria": "#52514e",
    "tinta_muted": "#898781",
    "grade": "#e1e0d9",
    "eixo": "#c3c2b7",
}

ESCURO = {
    "superficie": "#1a1a19",
    "plano": "#0d0d0d",
    "tinta_primaria": "#ffffff",
    "tinta_secundaria": "#c3c2b7",
    "tinta_muted": "#898781",
    "grade": "#2c2c2a",
    "eixo": "#383835",
}

# ----------------------------- Series categoricas -----------------------------
CATEGORICO_CLARO = ["#2a78d6", "#eb6834", "#1baf7a"]
CATEGORICO_ESCURO = ["#3987e5", "#d95926", "#199e70"]

# ----------------------------- Rampa ordinal (azul) -----------------------------
# alta -> media -> baixa, do mais escuro ao mais claro.
ORDINAL_CLARO = {"alta": "#184f95", "media": "#2a78d6", "baixa": "#86b6ef"}
ORDINAL_ESCURO = {"alta": "#cde2fb", "media": "#3987e5", "baixa": "#184f95"}

# ----------------------------- Status (fixo, nunca tematizado) -----------------
STATUS = {"bom": "#0ca30c", "atencao": "#fab219", "grave": "#ec835a", "critico": "#d03b3b"}


def paleta(escuro: bool = False) -> dict:
    """Devolve o conjunto completo de tokens para o modo pedido."""
    base = ESCURO if escuro else CLARO
    return {
        **base,
        "categorico": CATEGORICO_ESCURO if escuro else CATEGORICO_CLARO,
        "ordinal": ORDINAL_ESCURO if escuro else ORDINAL_CLARO,
        "status": STATUS,
        "sequencial": "#3987e5" if escuro else "#2a78d6",
    }


def aplicar_layout(figura, p: dict, altura: int = 330, mostrar_legenda: bool = False):
    """Aplica o enxoval padrao: grade recessiva, sem moldura, tinta correta.

    A legenda so aparece quando ha 2 ou mais series -- uma serie unica e nomeada
    pelo titulo do grafico, e a caixa de legenda vira ruido.
    """
    figura.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                  size=12, color=p["tinta_secundaria"]),
        showlegend=mostrar_legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=p["tinta_secundaria"], size=11)),
        hoverlabel=dict(bgcolor=p["superficie"], bordercolor=p["eixo"],
                        font=dict(color=p["tinta_primaria"], size=12)),
    )
    figura.update_xaxes(showgrid=False, zeroline=False,
                        linecolor=p["eixo"], tickfont=dict(color=p["tinta_muted"]))
    figura.update_yaxes(gridcolor=p["grade"], zeroline=False, linecolor="rgba(0,0,0,0)",
                        tickfont=dict(color=p["tinta_muted"]))
    return figura


def moeda(valor: float) -> str:
    """Formata em reais no padrao brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def compacto(valor: float) -> str:
    """Formata valores grandes de forma legivel em cartoes de destaque."""
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:.1f} mi".replace(".", ",")
    if abs(valor) >= 1_000:
        return f"R$ {valor / 1_000:.0f} mil"
    return moeda(valor)
