#!/usr/bin/env python3
"""Painel de Inteligencia Tributaria - MVP do Projeto Integrador (Eixo II).

Interface de demonstracao exigida pelo item 6.1.4 do plano de ensino.

    streamlit run app/painel.py

Seis abas:
    Visao Geral    panorama da carteira e da arrecadacao real coletada
    Cobranca       fila priorizada por retorno esperado
    Contribuinte   simulador individual com explicacao (LGPD Art. 20)
    Equidade       auditoria de fairness e simulacao de mitigacao
    Dados          proveniencia, esquema do banco e limitacoes
    Assistente     agente de IA que responde perguntas usando src/ferramentas.py
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

import assistente as assistente_ia  # noqa: E402
import config  # noqa: E402
from app import tema  # noqa: E402

st.set_page_config(page_title="Inteligencia Tributaria | Palmas-TO",
                   page_icon="■", layout="wide")


# --------------------------------------------------------------------------
# Carga de dados (em cache: o painel nao recalcula a cada interacao)
# --------------------------------------------------------------------------
ARTEFATOS = [config.BANCO, config.METRICAS, config.CSV_ARRECADACAO,
             config.DADOS / "fila_cobranca.csv", config.DADOS / "auditoria_fairness.json",
             config.DADOS / "mitigacao_fairness.csv", config.DADOS / "importancia_atributos.csv",
             config.DADOS / "teto_desempenho.json"]


def versao_dos_artefatos() -> tuple:
    """Data de modificacao de cada arquivo lido pelo painel.

    Entra como argumento de carregar(): quando o pipeline roda de novo, a versao
    muda e o cache e refeito. Sem isso, o painel aberto continuaria mostrando
    os resultados da execucao anterior ate o servidor ser reiniciado.
    """
    return tuple(a.stat().st_mtime_ns if a.exists() else None for a in ARTEFATOS)


@st.cache_data(max_entries=2)
def carregar(versao: tuple):  # versao so compoe a chave do cache
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

    teto = {}
    caminho_teto = config.DADOS / "teto_desempenho.json"
    if caminho_teto.exists():
        teto = json.loads(caminho_teto.read_text(encoding="utf-8"))

    return {"dados": dados, "fila": fila, "metricas": metricas, "auditoria": auditoria,
            "mitigacao": mitigacao, "importancia": importancia, "arrecadacao": arrecadacao,
            "teto": teto}


def modo_escuro() -> bool:
    try:
        return st.get_option("theme.base") == "dark"
    except Exception:
        return False


P = tema.paleta(modo_escuro())

pacote = carregar(versao_dos_artefatos())
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

aba_geral, aba_cobranca, aba_contribuinte, aba_equidade, aba_dados, aba_assistente = st.tabs(
    ["Visão Geral", "Fila de Cobrança", "Contribuinte", "Equidade", "Dados e Limites",
     "Assistente"])


# ==========================================================================
# Visao Geral
# ==========================================================================
with aba_geral:
    com_divida = dados[dados["valor_divida_consolidada"] > 0]

    # Cada cartao mostra a carteira inteira e, abaixo, a parte que entra na fila
    # de cobranca (sem os beneficiarios do IPTU Social). O percentual recuperavel
    # usa a MESMA base da fila: dividir o retorno da fila pela divida da carteira
    # inteira subestimaria a recuperacao.
    na_fila = com_divida[com_divida["iptu_social"] == 0]
    divida_total = com_divida["valor_divida_consolidada"].sum()
    divida_fila = na_fila["valor_divida_consolidada"].sum()
    protegidos = int(dados["iptu_social"].sum())

    # Os textos abaixo dos valores sao composicao, nao variacao: sem seta e sem cor.
    sem_seta = {"delta_color": "off", "delta_arrow": "off"}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Imóveis na carteira", tema.milhar(len(dados)),
              f"{tema.milhar(protegidos)} no IPTU Social", **sem_seta)
    c2.metric("Com dívida inscrita", tema.milhar(len(com_divida)),
              f"{tema.milhar(len(na_fila))} na fila de cobrança", **sem_seta,
              help=f"{tema.percentual(len(com_divida) / len(dados))} da carteira. A fila de "
                   f"cobrança exclui os {tema.milhar(len(com_divida) - len(na_fila))} "
                   "beneficiários do IPTU Social que têm dívida.")
    c3.metric("Dívida ativa", tema.compacto(divida_total),
              f"{tema.compacto(divida_fila)} na fila de cobrança", **sem_seta)
    if fila is not None:
        retorno = fila["retorno_esperado"].sum()
        c4.metric("Retorno esperado", tema.compacto(retorno),
                  f"{tema.percentual(retorno / divida_fila)} da dívida na fila", **sem_seta,
                  help="Soma, na fila de cobrança, de dívida × probabilidade de "
                       "recuperação estimada pelo Modelo 2, que responde: "
                       f"\"{tema.MODELOS['recuperabilidade']['pergunta']}\"")

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
        st.markdown(tema.pergunta_do_modelo("recuperabilidade"))
        st.caption("retorno esperado = valor da dívida × probabilidade de recuperação. "
                   "Ordenar só pela probabilidade privilegiaria dívidas pequenas; só pelo "
                   "valor, dívidas incobráveis. O produto equilibra os dois.")

        f1, f2, f3 = st.columns([2, 2, 1])
        setores = ["(todos)"] + sorted(fila["setor_urbano"].unique().tolist())
        setor_escolhido = f1.selectbox("Setor urbano", setores)
        faixas = f2.multiselect("Faixa de recuperabilidade", tema.ORDEM_FAIXAS,
                                default=tema.ORDEM_FAIXAS, format_func=tema.rotulo_faixa)
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
            por_faixa = (filtrada.groupby("faixa_recuperabilidade")
                         .agg(casos=("id_contribuinte", "count"),
                              divida=("valor_divida_consolidada", "sum"),
                              retorno=("retorno_esperado", "sum"))
                         .reindex(tema.ORDEM_FAIXAS).fillna(0).reset_index())

            figura = go.Figure(go.Bar(
                x=por_faixa["faixa_recuperabilidade"].map(tema.rotulo_faixa),
                y=por_faixa["retorno"],
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
            for faixa in tema.ORDEM_FAIXAS:
                bloco = amostra[amostra["faixa_recuperabilidade"] == faixa]
                if bloco.empty:
                    continue
                figura.add_trace(go.Scatter(
                    x=bloco["valor_divida_consolidada"], y=bloco["prob_recuperacao"],
                    mode="markers", name=f"recuperabilidade {tema.rotulo_faixa(faixa)}",
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
        exibida = filtrada.head(int(quantidade))[colunas]
        st.dataframe(
            exibida.assign(faixa_recuperabilidade=exibida["faixa_recuperabilidade"]
                           .map(tema.rotulo_faixa)),
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

            st.markdown(tema.pergunta_do_modelo("inadimplencia"))
            st.metric("Probabilidade de inadimplência no próximo exercício", tema.percentual(prob_inad))

            st.markdown(tema.pergunta_do_modelo("recuperabilidade"))
            if divida > 0:
                modelo_rec = joblib.load(config.MODELO_RECUPERABILIDADE)
                prob_rec = float(modelo_rec.predict_proba(entrada)[0, 1])
                import modelo as mod

                faixa = mod.faixa_recuperabilidade(prob_rec)
                st.metric("Probabilidade de recuperação da dívida (12 meses)", tema.percentual(prob_rec),
                          f"faixa {tema.rotulo_faixa(faixa)}", delta_color="off",
                          delta_arrow="off")
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
                           format_func=lambda x: tema.MODELOS[x]["nome"])
        st.markdown(tema.pergunta_do_modelo(escolha))
        st.caption(f"{tema.MODELOS[escolha]['uso']} Na auditoria, um caso \"selecionado\" é "
                   f"um caso {tema.MODELOS[escolha]['selecionado']}.")
        bloco = auditoria[escolha]
        por_grupo = tema.ordenar_faixas(pd.DataFrame(bloco["por_grupo"]))
        dp = bloco["paridade_demografica"]
        eo = bloco["igualdade_oportunidade"]

        c1, c2 = st.columns(2)
        intervalo = bloco.get("intervalo_95", {})
        for coluna, teste, chave in ((c1, dp, "paridade_demografica"),
                                     (c2, eo, "igualdade_oportunidade")):
            aprovado = teste["aprovado"]
            ic = intervalo.get(chave)
            ajuda = None
            if ic:
                def virgula(x):
                    return f"{x:.3f}".replace(".", ",")
                ajuda = (f"Intervalo de confiança de 95% por bootstrap: "
                         f"{virgula(ic['ic_inferior'])} a {virgula(ic['ic_superior'])}; "
                         f"{ic['prob_acima_do_limite']:.0%} das reamostras acima de 0,10. "
                         "Mede a incerteza do conjunto de teste; a aprovação usa a "
                         "estimativa pontual.")
            coluna.metric(teste["metrica"], f"{teste['diferenca']:.3f}".replace(".", ","),
                          "dentro do limite (0,10)" if aprovado else "acima do limite (0,10)",
                          delta_color="green" if aprovado else "red", delta_arrow="off",
                          help=ajuda)

        if not (dp["aprovado"] and eo["aprovado"]):
            st.error(f"**Disparidade relevante detectada.** O grupo "
                     f"'{tema.rotulo_faixa(dp['grupo_mais_selecionado'])}' é selecionado "
                     f"com muito mais frequência que "
                     f"'{tema.rotulo_faixa(dp['grupo_menos_selecionado'])}'. "
                     f"Discussão e mitigação em `docs/RIA.md`, seção 2.")
        else:
            st.success("Ambos os testes ficaram dentro do limite de disparidade de 0,10 adotado. "
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
            st.markdown("**Mitigação: corte calibrado por grupo**")
            st.caption("Em vez de um corte único em 0,5, cada grupo recebe um corte que "
                       "iguala as taxas de seleção. Não exige retreinar o modelo e mantém "
                       "a decisão auditável, com o corte de cada grupo documentado.")
            mit = tema.ordenar_faixas(pacote["mitigacao"])

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
            with st.expander("Ver cortes calibrados"):
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
        for chave in ("inadimplencia", "recuperabilidade"):
            st.markdown(f"- {tema.pergunta_do_modelo(chave)} {tema.MODELOS[chave]['uso']}")
        teto = pacote["teto"]

        def decimal(valor) -> str:
            return f"{valor:.3f}".replace(".", ",") if valor is not None else "—"

        linhas = []
        for nome, bloco in metricas.items():
            alcancavel = teto.get(nome, {}).get("alcancavel", {}).get("roc_auc")
            linhas.append({
                "Modelo": tema.MODELOS[nome]["nome"],
                "Acurácia": decimal(bloco["acuracia"]), "Precisão": decimal(bloco["precisao"]),
                "Recall": decimal(bloco["recall"]), "F1": decimal(bloco["f1"]),
                "ROC-AUC": decimal(bloco["roc_auc"]),
                "Teto do ROC-AUC": decimal(alcancavel),
                "n (teste)": tema.milhar(bloco["n_teste"]),
            })
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)

        if teto:
            def roc(nome, versao):
                return decimal(teto[nome][versao]["roc_auc"])
            st.markdown(
                "**Por que existe um teto.** O gerador da carteira sintética embute ruído "
                "deliberado: um termo oculto, que representa o que nenhum cadastro registra "
                "(desemprego, doença), e o sorteio final de cada resultado — quem tem 70% de "
                "chance de pagar deixa de pagar em 3 de cada 10 casos. Um oráculo que conhece "
                "a fórmula do gerador e todos os seus atributos chega a ROC-AUC de "
                f"**{roc('inadimplencia', 'alcancavel')}** na inadimplência e "
                f"**{roc('recuperabilidade', 'alcancavel')}** na recuperabilidade; mesmo "
                "conhecendo também o ruído oculto, não passaria de "
                f"{roc('inadimplencia', 'absoluto')} e {roc('recuperabilidade', 'absoluto')}. "
                "Os dois modelos estão praticamente no teto. O Modelo 2 usa regressão "
                "logística, a mesma forma do gerador; com gradient boosting, que sobreajustava "
                "com poucos casos, ficava em 0,686. Deixar a faixa de renda de fora quase não "
                "custa desempenho: sem ela, o teto do Modelo 2 passa de 0,722 para 0,721.")
        st.caption("Um ROC-AUC acima do teto seria impossível de forma legítima: indicaria "
                   "vazamento de dados — o modelo usando informação do resultado ou do futuro "
                   "—, não qualidade. As métricas usam o corte de decisão de 0,5.")

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


# ==========================================================================
# Assistente (agente de IA sobre as ferramentas de src/ferramentas.py)
# ==========================================================================
SUGESTOES = {
    ":material/insights: Panorama da carteira": "Qual o panorama da carteira de dívida ativa?",
    ":material/format_list_numbered: Fila em Taquaralto":
        "Quais são os 5 primeiros da fila de cobrança no setor Taquaralto?",
    ":material/balance: Equidade do modelo":
        "O modelo de recuperabilidade trata as faixas de renda de forma equilibrada?",
    ":material/map: Setores com mais risco":
        "Quais setores têm a maior taxa de inadimplência e quanto de dívida concentram?",
}


def _segredos() -> dict:
    """Credenciais de .streamlit/secrets.toml, quando existir (nunca versionado)."""
    try:
        return {k: st.secrets[k] for k in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL")
                if k in st.secrets}
    except Exception:
        return {}


@st.cache_resource
def obter_assistente(chave: str, modelo_ia: str) -> assistente_ia.Assistente:
    return assistente_ia.Assistente(assistente_ia.ClienteOpenRouter(chave, modelo_ia))


def _texto_md(texto: str) -> str:
    """O Markdown do Streamlit le $...$ como formula: 'R$ 10 e R$ 20' quebraria."""
    return texto.replace("$", r"\$")


def mostrar_resposta(texto: str, chamadas: list[dict]) -> None:
    st.markdown(_texto_md(texto))
    if chamadas:
        with st.expander(f":material/build: {len(chamadas)} consulta(s) às ferramentas"):
            for chamada in chamadas:
                argumentos = json.dumps(chamada["argumentos"], ensure_ascii=False)
                st.markdown(f"**`{chamada['ferramenta']}`** `{argumentos}`")
                st.json(chamada["resultado"], expanded=False)


def nova_conversa() -> None:
    st.session_state.conversa_ia = []
    st.session_state.historico_ia = []
    st.session_state.pendente_ia = None


# Os callbacks guardam a pergunta ANTES da nova execucao do script. Assim ela e
# respondida antes de o cabecalho (custo) e as sugestoes serem desenhados, e a
# tela nao mostra estado da rodada anterior.
def _guardar_sugestao() -> None:
    escolha = st.session_state.get("sugestao_ia")
    if escolha:
        st.session_state.pendente_ia = SUGESTOES[escolha]


def _guardar_digitada() -> None:
    texto = (st.session_state.get("entrada_ia") or "").strip()
    if texto:
        st.session_state.pendente_ia = texto


with aba_assistente:
    st.markdown("### Assistente de análise")
    st.caption("Pergunte em linguagem natural. Um modelo de linguagem escolhe quais funções "
               "deste painel consultar e redige a resposta; os números vêm dessas funções, "
               "e cada consulta fica visível abaixo da resposta. Beneficiários do IPTU Social "
               "estão fora do alcance das ferramentas, por regra do código.")

    try:
        chave_ia, modelo_ia = assistente_ia.ler_configuracao(_segredos())
    except assistente_ia.ErroAssistente:
        st.info("Assistente desativado: falta a chave do OpenRouter. Crie o arquivo `.env` na "
                "raiz do projeto com a linha `OPENROUTER_API_KEY=...` (o arquivo está no "
                "`.gitignore`) e recarregue a página.")
    else:
        if "conversa_ia" not in st.session_state:
            nova_conversa()
        conversa = st.session_state.conversa_ia
        cabecalho_ia = st.container()   # preenchido no fim, com o custo ja atualizado

        for troca in conversa:
            with st.chat_message("user"):
                st.markdown(_texto_md(troca["pergunta"]))
            with st.chat_message("assistant"):
                mostrar_resposta(troca["texto"], troca["chamadas"])

        pergunta = st.session_state.pendente_ia
        st.session_state.pendente_ia = None
        if pergunta:
            with st.chat_message("user"):
                st.markdown(_texto_md(pergunta))
            with st.chat_message("assistant"):
                try:
                    with st.spinner("Consultando as ferramentas..."):
                        resposta = obter_assistente(chave_ia, modelo_ia).responder(
                            pergunta, st.session_state.historico_ia)
                except assistente_ia.ErroAssistente as erro:
                    st.error(f"Não foi possível obter a resposta: {erro}")
                else:
                    mostrar_resposta(resposta.texto, resposta.chamadas)
                    st.session_state.historico_ia = resposta.mensagens
                    conversa.append({"pergunta": pergunta, "texto": resposta.texto,
                                     "chamadas": resposta.chamadas,
                                     "custo_usd": resposta.uso["custo_usd"]})

        if not conversa:
            st.pills("Sugestões", list(SUGESTOES), label_visibility="collapsed",
                     key="sugestao_ia", on_change=_guardar_sugestao)
        st.chat_input("Pergunte sobre a carteira, a fila, um contribuinte ou a equidade",
                      submit_mode="disable", key="entrada_ia", on_submit=_guardar_digitada)

        with cabecalho_ia, st.container(horizontal=True, vertical_alignment="center"):
            custo = sum(t["custo_usd"] for t in conversa)
            st.caption(f"Modelo `{modelo_ia}` via OpenRouter · custo desta conversa: "
                       f"US\\$ {custo:.4f}")
            st.button("Nova conversa", icon=":material/refresh:", on_click=nova_conversa,
                      disabled=not conversa, width="content")

        st.caption("O assistente apoia a análise e não decide cobrança. Perguntas e consultas "
                   "ficam registradas em `data/assistente_auditoria.jsonl`.")

st.divider()
st.caption("PoC acadêmico · Projeto Integrador Eixo II · UFT — "
           "Coordenação: Prof. Dr. David Nadler Prata")
