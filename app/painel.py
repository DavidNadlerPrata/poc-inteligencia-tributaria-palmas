#!/usr/bin/env python3
"""Painel de Inteligencia Tributaria - MVP do Projeto Integrador (Eixo II).

Interface de demonstracao exigida pelo item 6.1.4 do plano de ensino.

    streamlit run app/painel.py

Cinco abas, uma por competencia avaliada:
    Visao Geral    panorama da carteira e da arrecadacao real coletada
    Cobranca       fila priorizada por retorno esperado
    Contribuinte   simulador individual com explicacao (LGPD Art. 20)
    Equidade       auditoria de fairness e simulacao de mitigacao
    Dados          proveniencia, esquema do banco e limitacoes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

import config  # noqa: E402
from app import tema  # noqa: E402

st.set_page_config(page_title="Inteligencia Tributaria | Palmas-TO",
                   page_icon="■", layout="wide")


# --------------------------------------------------------------------------
# Carga de dados (em cache: o painel nao recalcula a cada interacao)
# --------------------------------------------------------------------------
@st.cache_data
def carregar():
    import etl

    if not config.BANCO.exists():
        return None

    dados = etl.carregar_visao_analitica()

    fila = None
    caminho_fila = config.DADOS / "fila_cobranca.csv"
    if caminho_fila.exists():
        fila = pd.read_csv(caminho_fila, sep=";")

    metricas = {}
    if config.METRICAS.exists():
        metricas = json.loads(config.METRICAS.read_text(encoding="utf-8"))

    auditoria = {}
    caminho_auditoria = config.DADOS / "auditoria_fairness.json"
    if caminho_auditoria.exists():
        auditoria = json.loads(caminho_auditoria.read_text(encoding="utf-8"))

    mitigacao = None
    caminho_mitigacao = config.DADOS / "mitigacao_fairness.csv"
    if caminho_mitigacao.exists():
        mitigacao = pd.read_csv(caminho_mitigacao, sep=";")

    importancia = None
    caminho_importancia = config.DADOS / "importancia_atributos.csv"
    if caminho_importancia.exists():
        importancia = pd.read_csv(caminho_importancia, sep=";")

    arrecadacao = None
    if config.CSV_ARRECADACAO.exists():
        arrecadacao = pd.read_csv(config.CSV_ARRECADACAO, sep=";", dtype=str)

    return {"dados": dados, "fila": fila, "metricas": metricas, "auditoria": auditoria,
            "mitigacao": mitigacao, "importancia": importancia, "arrecadacao": arrecadacao}


def modo_escuro() -> bool:
    try:
        return st.get_option("theme.base") == "dark"
    except Exception:
        return False


P = tema.paleta(modo_escuro())

pacote = carregar()
if pacote is None:
    st.error("Banco de dados nao encontrado. Rode antes:  `python executar_poc.py`")
    st.stop()

dados = pacote["dados"]
fila = pacote["fila"]
metricas = pacote["metricas"]
auditoria = pacote["auditoria"]

st.title("Inteligência Tributária — Palmas-TO")
st.caption("Predição de inadimplência e priorização da dívida ativa · "
           "Projeto Integrador, Eixo II — Bacharelado Interdisciplinar em IA / UFT")

aba_geral, aba_cobranca, aba_contribuinte, aba_equidade, aba_dados = st.tabs(
    ["Visão Geral", "Fila de Cobrança", "Contribuinte", "Equidade", "Dados e Limites"])


# ==========================================================================
# Visao Geral
# ==========================================================================
with aba_geral:
    com_divida = dados[dados["valor_divida_consolidada"] > 0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Imóveis na carteira", f"{len(dados):,}".replace(",", "."))
    c2.metric("Com dívida inscrita", f"{len(com_divida):,}".replace(",", "."),
              f"{len(com_divida) / len(dados):.1%} da carteira")
    c3.metric("Dívida ativa", tema.compacto(com_divida["valor_divida_consolidada"].sum()))
    if fila is not None:
        c4.metric("Retorno esperado", tema.compacto(fila["retorno_esperado"].sum()),
                  f"{fila['retorno_esperado'].sum() / com_divida['valor_divida_consolidada'].sum():.1%} recuperável")

    st.divider()
    col_esq, col_dir = st.columns(2)

    # --- Inadimplencia por setor: barra horizontal, serie unica ---
    with col_esq:
        st.markdown("**Taxa de inadimplência por setor urbano**")
        por_setor = (dados.groupby("setor_urbano")
                     .agg(taxa=("inadimplente_proximo_exercicio", "mean"),
                          imoveis=("id_contribuinte", "count"),
                          divida=("valor_divida_consolidada", "sum"))
                     .sort_values("taxa").reset_index())

        figura = go.Figure(go.Bar(
            x=por_setor["taxa"], y=por_setor["setor_urbano"], orientation="h",
            marker=dict(color=P["sequencial"], cornerradius=4),
            width=0.62,
            customdata=por_setor[["imoveis", "divida"]],
            hovertemplate="<b>%{y}</b><br>Inadimplência: %{x:.1%}"
                          "<br>Imóveis: %{customdata[0]:,}<extra></extra>",
        ))
        figura.update_xaxes(tickformat=".0%")
        st.plotly_chart(tema.aplicar_layout(figura, P, 340), use_container_width=True)
        with st.expander("Ver tabela"):
            st.dataframe(por_setor, use_container_width=True, hide_index=True)

    # --- Concentracao do retorno (curva de Pareto): linha, serie unica ---
    with col_dir:
        st.markdown("**Concentração do retorno esperado**")
        if fila is not None:
            ordenada = fila.sort_values("retorno_esperado", ascending=False)
            acumulado = ordenada["retorno_esperado"].cumsum() / ordenada["retorno_esperado"].sum()
            percentual_casos = pd.Series(range(1, len(ordenada) + 1)) / len(ordenada)

            passo = max(1, len(ordenada) // 400)
            figura = go.Figure(go.Scatter(
                x=percentual_casos[::passo] * 100, y=acumulado.to_numpy()[::passo] * 100,
                mode="lines", line=dict(color=P["sequencial"], width=2),
                hovertemplate="%{x:.0f}% dos casos concentram "
                              "%{y:.0f}% do retorno<extra></extra>",
            ))
            figura.add_shape(type="line", x0=0, y0=0, x1=100, y1=100,
                             line=dict(color=P["eixo"], width=1, dash="dot"))
            figura.add_annotation(x=72, y=62, text="distribuição uniforme",
                                  showarrow=False, font=dict(color=P["tinta_muted"], size=11))
            figura.update_xaxes(title="% dos contribuintes priorizados", ticksuffix="%")
            figura.update_yaxes(title="% do retorno esperado", ticksuffix="%")
            st.plotly_chart(tema.aplicar_layout(figura, P, 340), use_container_width=True)

            top20 = int(len(ordenada) * 0.2)
            captura = ordenada.head(top20)["retorno_esperado"].sum() / ordenada["retorno_esperado"].sum()
            st.caption(f"Concentrando esforço nos 20% melhores casos, a Sefin alcança "
                       f"**{captura:.0%}** do retorno esperado total.")

    # --- Arrecadacao real coletada da API ---
    if pacote["arrecadacao"] is not None:
        st.divider()
        st.markdown("**Arrecadação mensal — dados reais coletados da API da Prefeitura**")
        arrecadacao = pacote["arrecadacao"].copy()
        arrecadacao["mes"] = pd.to_numeric(arrecadacao["mes"], errors="coerce")
        arrecadacao["valor_arrecado_mes"] = pd.to_numeric(
            arrecadacao["valor_arrecado_mes"], errors="coerce").fillna(0)

        # Somente o nivel raiz da hierarquia, para nao contar o mesmo dinheiro varias vezes.
        raiz = arrecadacao[arrecadacao["descricao"].str.upper().str.strip()
                           .isin(["RECEITAS CORRENTES", "RECEITAS DE CAPITAL"])]
        serie = raiz.groupby("mes")["valor_arrecado_mes"].sum().reset_index().sort_values("mes")

        if not serie.empty:
            figura = go.Figure(go.Scatter(
                x=serie["mes"], y=serie["valor_arrecado_mes"], mode="lines+markers",
                line=dict(color=P["sequencial"], width=2),
                marker=dict(size=8, color=P["sequencial"],
                            line=dict(width=2, color=P["superficie"])),
                hovertemplate="Mês %{x}<br>Arrecadado: R$ %{y:,.0f}<extra></extra>",
            ))
            figura.update_xaxes(title="Mês de 2025", dtick=1)
            figura.update_yaxes(title="Arrecadação (R$)")
            st.plotly_chart(tema.aplicar_layout(figura, P, 300), use_container_width=True)
            st.caption("Fonte: portal de transparência de Palmas (`sgreceitas/listar`), "
                       "somando apenas o nível raiz da hierarquia de receitas.")


# ==========================================================================
# Fila de Cobranca
# ==========================================================================
with aba_cobranca:
    if fila is None:
        st.warning("Fila não gerada. Rode `python executar_poc.py`.")
    else:
        st.markdown("### Priorização por retorno esperado")
        st.caption("retorno esperado = valor da dívida × probabilidade de recuperação. "
                   "Ordenar só pela probabilidade privilegiaria dívidas pequenas; só pelo "
                   "valor, dívidas incobráveis. O produto equilibra os dois.")

        f1, f2, f3 = st.columns([2, 2, 1])
        setores = ["(todos)"] + sorted(fila["setor_urbano"].unique().tolist())
        setor_escolhido = f1.selectbox("Setor urbano", setores)
        faixas = f2.multiselect("Faixa de recuperabilidade", ["alta", "media", "baixa"],
                                default=["alta", "media", "baixa"])
        quantidade = f3.number_input("Exibir", 10, 500, 25, step=5)

        filtrada = fila.copy()
        if setor_escolhido != "(todos)":
            filtrada = filtrada[filtrada["setor_urbano"] == setor_escolhido]
        if faixas:
            filtrada = filtrada[filtrada["faixa_recuperabilidade"].isin(faixas)]

        m1, m2, m3 = st.columns(3)
        m1.metric("Casos selecionados", f"{len(filtrada):,}".replace(",", "."))
        m2.metric("Dívida envolvida", tema.compacto(filtrada["valor_divida_consolidada"].sum()))
        m3.metric("Retorno esperado", tema.compacto(filtrada["retorno_esperado"].sum()))

        st.divider()
        col_a, col_b = st.columns([1, 1])

        # --- Faixas de recuperabilidade: rampa ordinal de uma hue ---
        with col_a:
            st.markdown("**Carteira por faixa de recuperabilidade**")
            ordem = ["alta", "media", "baixa"]
            por_faixa = (filtrada.groupby("faixa_recuperabilidade")
                         .agg(casos=("id_contribuinte", "count"),
                              divida=("valor_divida_consolidada", "sum"),
                              retorno=("retorno_esperado", "sum"))
                         .reindex(ordem).fillna(0).reset_index())

            figura = go.Figure(go.Bar(
                x=por_faixa["faixa_recuperabilidade"], y=por_faixa["retorno"],
                marker=dict(color=[P["ordinal"][f] for f in por_faixa["faixa_recuperabilidade"]],
                            cornerradius=4),
                width=0.55,
                customdata=por_faixa[["casos", "divida"]],
                hovertemplate="<b>Recuperabilidade %{x}</b><br>Retorno esperado: R$ %{y:,.0f}"
                              "<br>Casos: %{customdata[0]:,}<extra></extra>",
            ))
            figura.update_yaxes(title="Retorno esperado (R$)")
            st.plotly_chart(tema.aplicar_layout(figura, P, 300), use_container_width=True)

        # --- Divida x probabilidade, por faixa ---
        with col_b:
            st.markdown("**Dívida × probabilidade de recuperação**")
            amostra = filtrada.sample(min(1200, len(filtrada)), random_state=config.SEMENTE)
            figura = go.Figure()
            for faixa in ["alta", "media", "baixa"]:
                bloco = amostra[amostra["faixa_recuperabilidade"] == faixa]
                if bloco.empty:
                    continue
                figura.add_trace(go.Scatter(
                    x=bloco["valor_divida_consolidada"], y=bloco["prob_recuperacao"],
                    mode="markers", name=f"recuperabilidade {faixa}",
                    marker=dict(size=8, color=P["ordinal"][faixa], opacity=0.55,
                                line=dict(width=2, color=P["superficie"])),
                    hovertemplate="Dívida: R$ %{x:,.0f}<br>P(recuperação): "
                                  "%{y:.1%}<extra></extra>",
                ))
            figura.update_xaxes(title="Dívida consolidada (R$)")
            figura.update_yaxes(title="P(recuperação)", tickformat=".0%")
            st.plotly_chart(tema.aplicar_layout(figura, P, 300, mostrar_legenda=True),
                            use_container_width=True)

        st.markdown("**Fila priorizada**")
        colunas = ["setor_urbano", "tipo_imovel", "valor_divida_consolidada",
                   "tempo_inadimplencia_dias", "prob_recuperacao",
                   "faixa_recuperabilidade", "retorno_esperado"]
        st.dataframe(
            filtrada.head(int(quantidade))[colunas],
            use_container_width=True, hide_index=True,
            column_config={
                "setor_urbano": "Setor",
                "tipo_imovel": "Tipo",
                "valor_divida_consolidada": st.column_config.NumberColumn("Dívida", format="R$ %.2f"),
                "tempo_inadimplencia_dias": st.column_config.NumberColumn("Dias inadimpl."),
                "prob_recuperacao": st.column_config.ProgressColumn(
                    "P(recuperação)", format="%.1f%%", min_value=0, max_value=1),
                "faixa_recuperabilidade": "Faixa",
                "retorno_esperado": st.column_config.NumberColumn("Retorno esperado", format="R$ %.2f"),
            })
        st.caption("Beneficiários do IPTU Social já foram excluídos desta fila, "
                   "conforme a seção 11 do plano de ensino.")


# ==========================================================================
# Contribuinte (simulador + explicacao)
# ==========================================================================
with aba_contribuinte:
    st.markdown("### Simulador de análise individual")
    st.caption("Demonstra o direito à explicação (LGPD, Art. 20): toda classificação "
               "vem acompanhada dos fatores que a determinaram.")

    col_entrada, col_saida = st.columns([1, 1])

    with col_entrada:
        setor = st.selectbox("Setor urbano", sorted(dados["setor_urbano"].unique()))
        tipo = st.selectbox("Tipo de imóvel", sorted(dados["tipo_imovel"].unique()))
        valor_venal = st.number_input("Valor venal (R$)", 10_000.0, 5_000_000.0, 180_000.0, 10_000.0)
        area = st.number_input("Área construída (m²)", 0.0, 2_000.0, 110.0, 10.0)
        distancia = st.slider("Distância do centro (km)", 0.0, 30.0, 8.0, 0.5)
        exercicios = st.slider("Exercícios inadimplentes (5 anos)", 0, 5, 2)
        tempo = st.slider("Tempo de inadimplência (dias)", 0, 3000, 540, 30)
        divida = st.number_input("Dívida consolidada (R$)", 0.0, 500_000.0, 4_800.0, 100.0)
        parcelamentos = st.slider("Parcelamentos anteriores", 0, 5, 1)
        rompido = st.checkbox("Parcelamento rompido")
        notificacoes = st.slider("Notificações recebidas", 0, 10, 2)
        social = st.checkbox("Beneficiário do IPTU Social")

    with col_saida:
        if social:
            st.info("**Contribuinte protegido pelo IPTU Social.**\n\n"
                    "Idosos, aposentados, pensionistas e pessoas com deficiência de baixa "
                    "renda são isentos e ficam fora das ações preditivas de cobrança. "
                    "O sistema não emite score para este contribuinte.")
        else:
            import joblib

            entrada = pd.DataFrame([{
                "tipo_imovel": tipo, "setor_urbano": setor,
                "area_construida_m2": area, "valor_venal": valor_venal,
                "valor_iptu_anual": valor_venal * 0.006, "distancia_centro_km": distancia,
                "exercicios_inadimplentes_5a": exercicios,
                "tempo_inadimplencia_dias": tempo,
                "valor_divida_consolidada": divida,
                "qtd_parcelamentos_anteriores": parcelamentos,
                "parcelamento_rompido": int(rompido),
                "qtd_notificacoes": notificacoes,
            }])

            modelo_inad = joblib.load(config.MODELO_INADIMPLENCIA)
            prob_inad = float(modelo_inad.predict_proba(entrada)[0, 1])

            st.metric("Probabilidade de inadimplência no próximo exercício", f"{prob_inad:.1%}")

            if divida > 0:
                modelo_rec = joblib.load(config.MODELO_RECUPERABILIDADE)
                prob_rec = float(modelo_rec.predict_proba(entrada)[0, 1])
                import modelo as mod

                faixa = mod.faixa_recuperabilidade(prob_rec)
                st.metric("Probabilidade de recuperação da dívida (12 meses)", f"{prob_rec:.1%}",
                          f"faixa {faixa}")
                st.metric("Retorno esperado", tema.moeda(divida * prob_rec))
            else:
                st.caption("Sem dívida inscrita: o modelo de recuperabilidade não se aplica.")

            st.divider()
            st.markdown("**Por que esta classificação?**")
            if pacote["importancia"] is not None:
                topo = pacote["importancia"].head(6)
                figura = go.Figure(go.Bar(
                    x=topo["importancia"], y=topo["atributo"], orientation="h",
                    marker=dict(color=P["sequencial"], cornerradius=4), width=0.6,
                    hovertemplate="<b>%{y}</b><br>Impacto: %{x:.4f}<extra></extra>",
                ))
                figura.update_yaxes(autorange="reversed")
                figura.update_xaxes(title="queda de ROC-AUC ao embaralhar o atributo")
                st.plotly_chart(tema.aplicar_layout(figura, P, 260), use_container_width=True)
                st.caption("Importância por permutação: mede quanto o modelo perde de "
                           "desempenho quando cada atributo é embaralhado. "
                           "É a base da explicação devida ao contribuinte.")


# ==========================================================================
# Equidade
# ==========================================================================
with aba_equidade:
    st.markdown("### Auditoria de justiça algorítmica")
    st.caption("Grupo protegido: faixa de renda predominante do setor urbano "
               "(proxy do setor censitário do IBGE).")

    if not auditoria:
        st.warning("Auditoria não encontrada. Rode `python executar_poc.py`.")
    else:
        escolha = st.radio("Modelo auditado", ["recuperabilidade", "inadimplencia"],
                           horizontal=True,
                           format_func=lambda x: ("Modelo 2 — recuperabilidade"
                                                  if x == "recuperabilidade"
                                                  else "Modelo 1 — inadimplência"))
        bloco = auditoria[escolha]
        por_grupo = pd.DataFrame(bloco["por_grupo"])
        dp = bloco["paridade_demografica"]
        eo = bloco["igualdade_oportunidade"]

        c1, c2 = st.columns(2)
        for coluna, teste in ((c1, dp), (c2, eo)):
            aprovado = teste["aprovado"]
            coluna.metric(teste["metrica"], f"{teste['diferenca']:.3f}",
                          "dentro do limiar (0,10)" if aprovado else "acima do limiar (0,10)",
                          delta_color="normal" if aprovado else "inverse")

        if not (dp["aprovado"] and eo["aprovado"]):
            st.error(f"**Disparidade relevante detectada.** O grupo "
                     f"'{dp['grupo_mais_selecionado']}' é selecionado com muito mais "
                     f"frequência que '{dp['grupo_menos_selecionado']}'. "
                     f"Discussão e mitigação em `docs/RIA.md`, seção 2.")
        else:
            st.success("Ambos os testes ficaram dentro do limiar de 0,10 adotado. "
                       "A auditoria permanece obrigatória a cada retreino.")

        st.divider()
        st.markdown("**Taxa de seleção e recall por grupo**")
        figura = go.Figure()
        figura.add_trace(go.Bar(
            x=por_grupo["grupo"], y=por_grupo["taxa_selecao"], name="taxa de seleção",
            marker=dict(color=P["categorico"][0], cornerradius=4), width=0.3,
            hovertemplate="<b>%{x}</b><br>Taxa de seleção: %{y:.1%}<extra></extra>"))
        figura.add_trace(go.Bar(
            x=por_grupo["grupo"], y=por_grupo["tpr_recall"], name="recall (TPR)",
            marker=dict(color=P["categorico"][1], cornerradius=4), width=0.3,
            hovertemplate="<b>%{x}</b><br>Recall: %{y:.1%}<extra></extra>"))
        figura.update_layout(bargap=0.35, bargroupgap=0.08)
        figura.update_yaxes(tickformat=".0%")
        st.plotly_chart(tema.aplicar_layout(figura, P, 320, mostrar_legenda=True),
                        use_container_width=True)

        with st.expander("Ver tabela completa por grupo"):
            st.dataframe(por_grupo, use_container_width=True, hide_index=True)

        if pacote["mitigacao"] is not None and escolha == "recuperabilidade":
            st.divider()
            st.markdown("**Mitigação: limiar calibrado por grupo**")
            st.caption("Em vez de um corte único em 0,5, cada grupo recebe um limiar que "
                       "iguala as taxas de seleção. Não exige retreinar o modelo e mantém "
                       "a decisão auditável, com o limiar de cada grupo documentado.")
            mit = pacote["mitigacao"]

            figura = go.Figure()
            figura.add_trace(go.Bar(
                x=mit["grupo"], y=mit["taxa_selecao_antes"], name="antes",
                marker=dict(color=P["categorico"][0], cornerradius=4), width=0.3,
                hovertemplate="<b>%{x}</b><br>Antes: %{y:.1%}<extra></extra>"))
            figura.add_trace(go.Bar(
                x=mit["grupo"], y=mit["taxa_selecao_depois"], name="depois da calibração",
                marker=dict(color=P["categorico"][1], cornerradius=4), width=0.3,
                hovertemplate="<b>%{x}</b><br>Depois: %{y:.1%}<extra></extra>"))
            figura.update_layout(bargap=0.35, bargroupgap=0.08)
            figura.update_yaxes(tickformat=".0%", title="taxa de seleção")
            st.plotly_chart(tema.aplicar_layout(figura, P, 300, mostrar_legenda=True),
                            use_container_width=True)

            antes = mit["taxa_selecao_antes"]
            depois = mit["taxa_selecao_depois"]
            st.caption(f"Disparidade na taxa de seleção: **{antes.max() - antes.min():.4f}** → "
                       f"**{depois.max() - depois.min():.4f}** após a calibração.")
            with st.expander("Ver limiares calibrados"):
                st.dataframe(mit, use_container_width=True, hide_index=True)


# ==========================================================================
# Dados e Limites
# ==========================================================================
with aba_dados:
    st.markdown("### Proveniência dos dados")

    st.markdown("""
**Dados reais** — coletados da API REST pública da Prefeitura de Palmas
(`sgreceitas/listar` no portal de transparência). São os agregados de
arrecadação por código de receita, órgão e mês. O script de coleta está em
`src/coleta.py`, com paginação, retry e pausa entre requisições.

**Dados sintéticos** — a carteira de contribuintes (`src/sintetico.py`). O
registro individual de dívida ativa **não é público**: é dado pessoal protegido
pela LGPD e só pode ser obtido mediante convênio formal com a Sefin. A carteira
é gerada por um processo calibrado pelos agregados oficiais e reproduz a
estrutura de colunas de um cadastro imobiliário municipal.
    """)

    if metricas:
        st.divider()
        st.markdown("### Desempenho dos modelos")
        linhas = []
        for nome, bloco in metricas.items():
            linhas.append({
                "Modelo": ("Inadimplência" if nome == "inadimplencia" else "Recuperabilidade"),
                "Acurácia": bloco["acuracia"], "Precisão": bloco["precisao"],
                "Recall": bloco["recall"], "F1": bloco["f1"], "ROC-AUC": bloco["roc_auc"],
                "n (teste)": bloco["n_teste"],
            })
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
        st.caption("Desempenho moderado é esperado e honesto: o processo gerador embute "
                   "ruído deliberado. Números próximos de 1,0 num PoC como este indicariam "
                   "vazamento de dados, não qualidade.")

    st.divider()
    st.markdown("### Limitações — leia antes de usar em decisão real")
    st.warning("""
1. **A carteira é sintética.** Os números do painel demonstram o funcionamento do
   sistema, não a situação fiscal real de Palmas.
2. **Correlação não é causalidade.** O modelo aprende padrões históricos; um score
   alto não significa que o contribuinte *deva* ser cobrado com mais rigor.
3. **Viés herdado.** O histórico de cobrança reflete decisões humanas passadas,
   possivelmente enviesadas. O modelo tende a reproduzi-las.
4. **Decisão assistida, nunca automática.** O sistema ordena uma fila de trabalho.
   A decisão fiscal permanece com o servidor público responsável.
5. **Direito à contestação.** Todo contribuinte pode contestar sua classificação,
   conforme o Art. 20 da LGPD.
    """)

    st.divider()
    st.markdown("### Esquema do banco")
    st.code("""setor_urbano (1) ──< imovel (1) ──< divida_ativa
                          │
                          └──< historico_cobranca

arrecadacao_mensal   -- série agregada real, coletada da API""", language="text")

    with st.expander("Ver amostra da visão analítica"):
        st.dataframe(dados.head(50), use_container_width=True, hide_index=True)

st.divider()
st.caption("PoC acadêmico · Projeto Integrador Eixo II · UFT — "
           "Coordenação: Prof. Dr. David Nadler Prata")
