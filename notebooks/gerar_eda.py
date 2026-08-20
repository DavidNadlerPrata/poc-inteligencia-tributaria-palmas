#!/usr/bin/env python3
"""Gera o notebook de EDA da Sprint 2 (`eda_sprint2.ipynb`).

Manter o notebook como script gerador tem duas vantagens: o conteudo fica
versionavel em texto limpo (diff legivel no Git) e o .ipynb pode ser
reconstruido e reexecutado a qualquer momento.

    python notebooks/gerar_eda.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "notebooks" / "eda_sprint2.ipynb"


def md(texto: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(texto.strip())


def code(texto: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(texto.strip())


celulas = [

md("""
# Análise Exploratória de Dados — Sprint 2

**Projeto Integrador do Eixo II** · Opção D — Inteligência Tributária de Palmas-TO
Módulo âncora: M5 — Coleta e Transformação de Dados

---

## Objetivo

Entender os dados **antes** de modelar. Toda decisão da Sprint 3 (escolha de
algoritmo, atributos, variável-alvo) deve nascer de uma evidência encontrada
aqui — não do contrário.

Este notebook responde a cinco perguntas:

1. O que a API da Prefeitura realmente entrega?
2. Que armadilhas os dados escondem?
3. Como a dívida ativa se distribui na carteira?
4. Quais atributos têm relação com inadimplência e com recuperação?
5. O que isso tudo recomenda para a modelagem?
"""),

code("""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

import config
import etl

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 30)

# Paleta validada (ver app/tema.py): azul, laranja, aqua.
AZUL, LARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, MUTED, GRADE = "#0b0b0b", "#898781", "#e1e0d9"

plt.rcParams.update({
    "figure.figsize": (9, 4),
    "figure.dpi": 110,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": "#52514e",
    "axes.grid": True,
    "grid.color": GRADE,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "font.size": 10,
})
print("ambiente pronto")
"""),

md("""
---
## 1. Os dados reais coletados da API

Coletados por `src/coleta.py` no portal de transparência de Palmas
(`POST /api`, ação `sgreceitas/listar`). São **agregados de arrecadação** —
valor por código de receita, órgão e mês.
"""),

code("""
arrecadacao = pd.read_csv(config.CSV_ARRECADACAO, sep=";", dtype=str)

print(f"registros: {len(arrecadacao):,}")
print(f"colunas:   {list(arrecadacao.columns)}")
arrecadacao.head(3)
"""),

code("""
# Tipagem: a API devolve tudo como texto.
num = ["ano", "mes", "valor_orcado", "valor_arrecado_mes", "valor_arrecado_periodo"]
for coluna in num:
    arrecadacao[coluna] = pd.to_numeric(arrecadacao[coluna], errors="coerce")

print("Valores ausentes por coluna:")
print(arrecadacao.isna().sum()[lambda s: s > 0].to_string() or "  (nenhum)")
print(f"\\nPeríodo coberto: {arrecadacao['ano'].min():.0f}, "
      f"meses {arrecadacao['mes'].min():.0f} a {arrecadacao['mes'].max():.0f}")
print(f"Códigos de receita distintos: {arrecadacao['codigo'].nunique():,}")
print(f"Órgãos: {arrecadacao['orgao_nome'].nunique()}")
"""),

md("""
### 1.1 A armadilha da hierarquia — leia antes de somar qualquer coisa

O código de receita é **hierárquico**: `1.0.0.0.00.0.0` (RECEITAS CORRENTES) é o
agregado de `1.1.0.0.00.0.0` (Impostos), que por sua vez agrega os níveis
abaixo. A listagem devolve **todos os níveis juntos**.

Somar a coluna inteira conta o mesmo dinheiro várias vezes. Este é o erro
número um de quem consome essa API pela primeira vez.
"""),

code("""
def nivel_hierarquico(codigo: str) -> int:
    \"\"\"Profundidade do código: conta os segmentos não nulos antes dos zeros.\"\"\"
    partes = str(codigo).split(".")
    nivel = 0
    for parte in partes:
        if parte.strip("0") == "":
            break
        nivel += 1
    return nivel

arrecadacao["nivel"] = arrecadacao["codigo"].map(nivel_hierarquico)

comparacao = (arrecadacao.groupby("nivel")
              .agg(registros=("codigo", "size"),
                   total=("valor_arrecado_mes", "sum"))
              .assign(total_bilhoes=lambda d: (d["total"] / 1e9).round(3)))

print("Soma por nível hierárquico:\\n")
print(comparacao[["registros", "total_bilhoes"]].to_string())

soma_ingenua = arrecadacao["valor_arrecado_mes"].sum()
soma_raiz = arrecadacao.loc[arrecadacao["nivel"] == 1, "valor_arrecado_mes"].sum()
print(f"\\nSoma ingênua (tudo):      R$ {soma_ingenua/1e9:,.2f} bi")
print(f"Soma correta (só raiz):   R$ {soma_raiz/1e9:,.2f} bi")
print(f"Fator de superestimação:  {soma_ingenua/soma_raiz:.1f}x")
"""),

md("""
> **Achado 1.** Somar a coluna sem filtrar o nível hierárquico superestima a
> arrecadação em várias vezes. Toda agregação neste projeto deve fixar um nível
> ou usar apenas as folhas da árvore.
"""),

code("""
# Série mensal correta: apenas o nível raiz.
raiz = arrecadacao[arrecadacao["nivel"] == 1]
serie = raiz.groupby("mes")["valor_arrecado_mes"].sum().sort_index()

figura, eixo = plt.subplots()
eixo.plot(serie.index, serie.values / 1e6, color=AZUL, linewidth=2,
          marker="o", markersize=7, markeredgecolor="white", markeredgewidth=2)
eixo.set_xlabel("Mês de 2025")
eixo.set_ylabel("Arrecadação (R$ milhões)")
eixo.set_title("Arrecadação mensal — dados reais da Prefeitura de Palmas",
               color=TINTA, loc="left")
eixo.set_xticks(range(1, 13))
plt.tight_layout()
plt.show()

print(f"Média mensal: R$ {serie.mean()/1e6:,.1f} mi")
print(f"Mês de pico:  {serie.idxmax():.0f} (R$ {serie.max()/1e6:,.1f} mi)")
print(f"Mês mais baixo: {serie.idxmin():.0f} (R$ {serie.min()/1e6:,.1f} mi)")
"""),

md("""
> **Achado 2 — uma anomalia a investigar antes de modelar.** Dezembro registra
> R$ 733 mi, quase **3× a média** dos demais meses (que ficam entre R$ 192 mi e
> R$ 267 mi). Um salto dessa magnitude no último mês do exercício não tem cara
> de sazonalidade tributária — sugere lançamentos de encerramento contábil ou
> operações de crédito concentradas no fechamento. Note que o nível raiz inclui
> `RECEITAS DE CAPITAL` e operações de crédito, que não são arrecadação
> corrente.
>
> **Não trate esse valor como receita tributária sem antes verificar sua
> natureza.** Incluí-lo numa projeção distorceria qualquer previsão. Este é o
> tipo de achado que justifica a EDA existir: o gráfico mostra o problema que a
> tabela esconderia.
"""),

code("""
# O IPTU tem calendário próprio? Vale separar do total.
iptu = arrecadacao[arrecadacao["descricao"].str.contains(
    "IPTU|PREDIAL|TERRITORIAL", case=False, na=False)]
serie_iptu = iptu.groupby("mes")["valor_arrecado_mes"].sum().sort_index()

figura, eixo = plt.subplots()
eixo.plot(serie_iptu.index, serie_iptu.values / 1e6, color=LARANJA, linewidth=2,
          marker="o", markersize=7, markeredgecolor="white", markeredgewidth=2)
eixo.set_xlabel("Mês de 2025")
eixo.set_ylabel("Arrecadação de IPTU (R$ milhões)")
eixo.set_title("IPTU tem sazonalidade própria, diferente da receita total",
               color=TINTA, loc="left")
eixo.set_xticks(range(1, 13))
plt.tight_layout()
plt.show()

print(f"rubricas de IPTU encontradas: {iptu['descricao'].nunique()}")
print(f"mês de pico do IPTU: {serie_iptu.idxmax():.0f} "
      f"(R$ {serie_iptu.max()/1e6:,.1f} mi)")
print(f"mês de pico da receita total: {serie.idxmax():.0f}")
"""),

md("""
> **Achado 3.** O IPTU tem sazonalidade **própria e distinta** da receita total:
> concentra-se em **março** (cota única e primeiras parcelas), com um segundo
> movimento em junho — enquanto a receita total pica em dezembro.
>
> Tratar "arrecadação" como bloco único apaga o fato de que cada tributo tem seu
> calendário. Para o problema de inadimplência de IPTU, o mês de referência é
> variável relevante, e a série a acompanhar é a do próprio tributo.
"""),

code("""
# Onde está o dinheiro: maiores rubricas do segundo nível.
nivel2 = (arrecadacao[arrecadacao["nivel"] == 2]
          .groupby("descricao")["valor_arrecado_mes"].sum()
          .sort_values(ascending=False).head(8))

figura, eixo = plt.subplots(figsize=(9, 4.2))
posicoes = np.arange(len(nivel2))
eixo.barh(posicoes, nivel2.values / 1e6, color=AZUL, height=0.62)
eixo.set_yticks(posicoes)
eixo.set_yticklabels([d[:42] for d in nivel2.index], fontsize=9)
eixo.invert_yaxis()
eixo.set_xlabel("Arrecadação no ano (R$ milhões)")
eixo.set_title("Principais rubricas de receita", color=TINTA, loc="left")
eixo.grid(axis="y", visible=False)
plt.tight_layout()
plt.show()
"""),

md("""
---
## 2. A carteira de contribuintes

Aqui está o limite do que é público. A predição de inadimplência exige o
**registro individual** — quem deve, quanto, há quanto tempo. Esse dado é
pessoal, protegido pela LGPD, e **não está publicado**.

A carteira usada a seguir é **sintética**, calibrada pelos agregados oficiais da
Sefin (R$ 363 mi de IPTU em dívida ativa, 111.252 imóveis tributáveis). Detalhes
em `src/sintetico.py` e em `docs/RIA.md`, seção 1.
"""),

code("""
dados = etl.carregar_visao_analitica()

print(f"contribuintes: {len(dados):,}")
print(f"colunas: {dados.shape[1]}")
print(f"\\nvalores ausentes: {int(dados.isna().sum().sum())}")
dados.head(3)
"""),

code("""
descricao = dados[["valor_venal", "valor_iptu_anual", "area_construida_m2",
                   "valor_divida_consolidada", "tempo_inadimplencia_dias",
                   "distancia_centro_km"]].describe().T
descricao["assimetria"] = dados[descricao.index].skew()
descricao[["mean", "50%", "max", "assimetria"]].round(2)
"""),

md("""
> **Achado 4.** `valor_venal` e `valor_divida_consolidada` têm **assimetria
> forte à direita**: a média fica muito acima da mediana. Poucos imóveis de alto
> valor puxam a média. Consequências práticas: usar a mediana para descrever a
> carteira, e preferir modelos baseados em árvores — que não se incomodam com
> distribuições assimétricas — a modelos lineares, que exigiriam transformação
> logarítmica.
"""),

code("""
figura, eixos = plt.subplots(1, 2, figsize=(10.5, 3.8))

com_divida = dados[dados["valor_divida_consolidada"] > 0]
eixos[0].hist(com_divida["valor_divida_consolidada"], bins=60, color=AZUL)
eixos[0].set_title("Dívida consolidada (escala original)", color=TINTA, loc="left", fontsize=10)
eixos[0].set_xlabel("R$")

eixos[1].hist(np.log10(com_divida["valor_divida_consolidada"]), bins=60, color=LARANJA)
eixos[1].set_title("Dívida consolidada (log₁₀)", color=TINTA, loc="left", fontsize=10)
eixos[1].set_xlabel("log₁₀(R$)")

for eixo in eixos:
    eixo.set_ylabel("imóveis")
plt.tight_layout()
plt.show()

print(f"mediana: R$ {com_divida['valor_divida_consolidada'].median():,.2f}")
print(f"média:   R$ {com_divida['valor_divida_consolidada'].mean():,.2f}")
"""),

md("""
### 2.1 Concentração da dívida

Uma pergunta central para a priorização: a dívida está espalhada ou concentrada?
"""),

code("""
ordenada = com_divida["valor_divida_consolidada"].sort_values(ascending=False)
acumulado = ordenada.cumsum() / ordenada.sum()
percentual = np.arange(1, len(ordenada) + 1) / len(ordenada)

figura, eixo = plt.subplots()
eixo.plot(percentual * 100, acumulado.values * 100, color=AZUL, linewidth=2)
eixo.plot([0, 100], [0, 100], color=MUTED, linewidth=1, linestyle=":")
eixo.annotate("distribuição uniforme", xy=(70, 63), color=MUTED, fontsize=9)
eixo.set_xlabel("% dos devedores (do maior para o menor)")
eixo.set_ylabel("% da dívida acumulada")
eixo.set_title("Concentração da dívida ativa", color=TINTA, loc="left")
plt.tight_layout()
plt.show()

for corte in (0.10, 0.20, 0.50):
    fatia = acumulado.iloc[int(len(ordenada) * corte) - 1]
    print(f"os {corte:.0%} maiores devedores concentram {fatia:.1%} da dívida")
"""),

md("""
> **Achado 5.** A dívida é **concentrada**: uma fração pequena dos devedores
> responde por parcela desproporcional do valor. Isso é o argumento quantitativo
> a favor de priorizar a cobrança — e sugere ordenar por **valor esperado**, não
> apenas por probabilidade de recuperação.
"""),

md("""
---
## 3. Inadimplência por segmento

Agora a parte sensível: como a inadimplência se distribui entre grupos.
"""),

code("""
por_renda = (dados.groupby("faixa_renda_setor")
             .agg(imoveis=("id_contribuinte", "count"),
                  inadimplencia=("inadimplente_proximo_exercicio", "mean"),
                  divida_media=("valor_divida_consolidada", "mean"),
                  divida_total=("valor_divida_consolidada", "sum"))
             .reindex(["baixa", "media", "alta"]))

print(por_renda.round(3).to_string())

figura, eixos = plt.subplots(1, 2, figsize=(10.5, 3.8))
posicoes = np.arange(len(por_renda))

eixos[0].bar(posicoes, por_renda["inadimplencia"] * 100, color=AZUL, width=0.55)
eixos[0].set_xticks(posicoes); eixos[0].set_xticklabels(por_renda.index)
eixos[0].set_ylabel("% inadimplentes")
eixos[0].set_title("Taxa de inadimplência", color=TINTA, loc="left", fontsize=10)
eixos[0].grid(axis="x", visible=False)

eixos[1].bar(posicoes, por_renda["divida_media"], color=LARANJA, width=0.55)
eixos[1].set_xticks(posicoes); eixos[1].set_xticklabels(por_renda.index)
eixos[1].set_ylabel("R$")
eixos[1].set_title("Dívida média por imóvel", color=TINTA, loc="left", fontsize=10)
eixos[1].grid(axis="x", visible=False)

for eixo in eixos:
    eixo.set_xlabel("faixa de renda do setor")
plt.tight_layout()
plt.show()
"""),

md("""
> **Achado 6 — o mais importante do notebook.** Os dois gráficos apontam em
> direções opostas:
>
> - setores de renda **baixa** têm a **maior taxa** de inadimplência;
> - setores de renda **alta** têm a **maior dívida média** por imóvel.
>
> Ou seja: **onde estão mais casos não é onde está mais dinheiro.** Um modelo
> treinado para prever *quem fica inadimplente* vai apontar para a população
> pobre. Um modelo treinado para prever *de quem se recupera dinheiro* pode
> apontar para outro lugar.
>
> Essa observação — feita na EDA, antes de qualquer modelagem — é o que motiva
> a decisão de projeto da Sprint 3: **usar dois modelos com papéis distintos** e
> deixar a priorização de cobrança a cargo do modelo de recuperabilidade.
"""),

code("""
por_setor = (dados.groupby("setor_urbano")
             .agg(imoveis=("id_contribuinte", "count"),
                  inadimplencia=("inadimplente_proximo_exercicio", "mean"),
                  divida_total=("valor_divida_consolidada", "sum"))
             .sort_values("inadimplencia"))

figura, eixo = plt.subplots(figsize=(9, 4))
posicoes = np.arange(len(por_setor))
eixo.barh(posicoes, por_setor["inadimplencia"] * 100, color=AZUL, height=0.62)
eixo.set_yticks(posicoes); eixo.set_yticklabels(por_setor.index, fontsize=9)
eixo.set_xlabel("% inadimplentes")
eixo.set_title("Inadimplência por setor urbano", color=TINTA, loc="left")
eixo.grid(axis="y", visible=False)
plt.tight_layout()
plt.show()
"""),

code("""
# Tipo de imovel
por_tipo = (dados.groupby("tipo_imovel")
            .agg(imoveis=("id_contribuinte", "count"),
                 inadimplencia=("inadimplente_proximo_exercicio", "mean"),
                 recuperacao=("divida_recuperada_12m", "mean"))
            .sort_values("inadimplencia", ascending=False))
por_tipo.round(3)
"""),

md("""
---
## 4. O que prevê o quê

Correlações entre atributos e os dois alvos candidatos.
"""),

code("""
numericas = ["area_construida_m2", "valor_venal", "valor_iptu_anual",
             "distancia_centro_km", "exercicios_inadimplentes_5a",
             "tempo_inadimplencia_dias", "valor_divida_consolidada",
             "qtd_parcelamentos_anteriores", "parcelamento_rompido",
             "qtd_notificacoes"]

alvos = ["inadimplente_proximo_exercicio", "divida_recuperada_12m"]
correlacoes = dados[numericas + alvos].corr()[alvos].drop(index=alvos)

comparativo = correlacoes.rename(columns={
    "inadimplente_proximo_exercicio": "inadimplência",
    "divida_recuperada_12m": "recuperação"}).round(3)
comparativo.reindex(comparativo["inadimplência"].abs().sort_values(ascending=False).index)
"""),

code("""
ordem = comparativo["inadimplência"].abs().sort_values().index
posicoes = np.arange(len(ordem))
altura = 0.38

figura, eixo = plt.subplots(figsize=(9, 5))
eixo.barh(posicoes - altura/2, comparativo.loc[ordem, "inadimplência"],
          height=altura, color=AZUL, label="inadimplência")
eixo.barh(posicoes + altura/2, comparativo.loc[ordem, "recuperação"],
          height=altura, color=LARANJA, label="recuperação")
eixo.axvline(0, color="#c3c2b7", linewidth=1)
eixo.set_yticks(posicoes); eixo.set_yticklabels(ordem, fontsize=9)
eixo.set_xlabel("correlação de Pearson com o alvo")
eixo.set_title("Correlação dos atributos com cada alvo", color=TINTA, loc="left")
eixo.legend(frameon=False, loc="lower right")
eixo.grid(axis="y", visible=False)
plt.tight_layout()
plt.show()
"""),

md("""
> **Achado 7.** Os dois alvos são governados por atributos **diferentes**:
>
> - a **inadimplência** responde ao histórico (`exercicios_inadimplentes_5a`) e
>   a características do imóvel;
> - a **recuperação** responde sobretudo ao `tempo_inadimplencia_dias`
>   (negativo: dívida velha recupera menos) e ao histórico de parcelamento.
>
> Note que a recuperação depende mais do **processo de cobrança** do que do
> perfil do contribuinte. É por isso que o modelo de recuperabilidade tende a
> ser mais equitativo — hipótese que a Sprint 4 vai testar formalmente.
"""),

code("""
# Relacao entre tempo de inadimplencia e taxa de recuperacao
faixas = pd.cut(com_divida["tempo_inadimplencia_dias"],
                bins=[0, 180, 365, 730, 1460, 10_000],
                labels=["até 6m", "6m-1a", "1-2a", "2-4a", "4a+"])
recuperacao = com_divida.groupby(faixas, observed=True)["divida_recuperada_12m"].agg(["mean", "size"])

figura, eixo = plt.subplots()
posicoes = np.arange(len(recuperacao))
eixo.bar(posicoes, recuperacao["mean"] * 100, color=AQUA, width=0.55)
eixo.set_xticks(posicoes); eixo.set_xticklabels(recuperacao.index)
eixo.set_xlabel("tempo desde a inscrição em dívida ativa")
eixo.set_ylabel("% recuperada em 12 meses")
eixo.set_title("Quanto mais velha a dívida, menor a chance de recuperação",
               color=TINTA, loc="left")
eixo.grid(axis="x", visible=False)
plt.tight_layout()
plt.show()

print(recuperacao.round(3).to_string())
"""),

md("""
> **Achado 8.** A taxa de recuperação **cai monotonicamente** com a idade da
> dívida. Isso tem implicação direta de política pública: **agir cedo vale mais
> que agir forte**. Uma cobrança administrativa nos primeiros seis meses tende a
> render mais que uma execução fiscal anos depois.
"""),

md("""
---
## 5. Grupos protegidos

O IPTU Social de Palmas isenta idosos, aposentados, pensionistas e PCD de baixa
renda. A seção 11 do plano de ensino é explícita: esse grupo **não pode ser alvo
das ações preditivas de cobrança**.
"""),

code("""
social = dados[dados["iptu_social"] == 1]

print(f"beneficiários: {len(social):,} ({len(social)/len(dados):.1%} da carteira)")
print(f"dívida associada: R$ {social['valor_divida_consolidada'].sum():,.2f}")
print("\\nDistribuição por faixa de renda do setor:")
print((social["faixa_renda_setor"].value_counts(normalize=True) * 100).round(1).to_string())
print("\\nComparação de taxa de inadimplência:")
print(f"  beneficiários:     {social['inadimplente_proximo_exercicio'].mean():.1%}")
print(f"  demais imóveis:    {dados[dados['iptu_social']==0]['inadimplente_proximo_exercicio'].mean():.1%}")
"""),

md("""
> **Achado 9.** Os beneficiários concentram-se em setores de renda baixa, como
> esperado. A exclusão desse grupo é uma **regra de negócio verificada por
> teste automatizado** (`tests/test_etica.py`), não uma recomendação — porque
> uma regra ética que depende da disciplina de quem opera o sistema
> eventualmente falha.
"""),

md("""
---
## 6. Conclusões e recomendações para a Sprint 3

| # | Achado | Consequência para a modelagem |
|---|--------|-------------------------------|
| 1 | Códigos de receita são hierárquicos (superestimação de 6,6×) | Fixar nível antes de agregar; nunca somar a coluna inteira |
| 2 | Pico atípico em dezembro na receita total | Investigar a natureza do valor antes de usar a série |
| 3 | IPTU tem sazonalidade própria (pico em março) | Mês como variável; acompanhar a série do próprio tributo |
| 4 | Valores fortemente assimétricos | Modelos de árvore em vez de lineares; mediana para descrever |
| 5 | Dívida concentrada em poucos devedores | Ordenar por valor esperado, não só por probabilidade |
| 6 | **Mais casos ≠ mais dinheiro** | **Dois modelos com papéis distintos; priorização pelo de recuperabilidade** |
| 7 | Alvos governados por atributos diferentes | Treinos separados, não um modelo multitarefa |
| 8 | Recuperação cai com a idade da dívida | `tempo_inadimplencia_dias` como atributo central; agir cedo |
| 9 | Grupo protegido concentrado em renda baixa | Excluir antes do treino, com teste automatizado |

### Decisões que a EDA sustenta

1. **Dois modelos, não um.** Achados 6 e 7.
2. **`HistGradientBoostingClassifier`.** Achado 4: assimetria e não linearidade
   sem exigir normalização.
3. **Priorizar por `valor_divida × P(recuperação)`.** Achado 5.
4. **Faixa de renda fora dos preditores.** Achado 6: correlação com renda existe
   e é justamente o que a auditoria da Sprint 4 precisa medir sem contaminação.
5. **Auditar os dois modelos separadamente.** A hipótese do achado 7 é que eles
   se comportarão de forma diferente — e é preciso verificar, não supor.

### Pendência aberta para a equipe

O **achado 2** não está resolvido: sabemos que dezembro é atípico, não sabemos
por quê. Investigar a composição desse valor (abrindo por código de receita e
por órgão) é uma tarefa concreta para a próxima iteração — e um bom exemplo de
que a EDA levanta perguntas, além de responder.

### Limitações desta análise

- A carteira é **sintética**. Os padrões refletem o processo gerador calibrado,
  não a realidade fiscal de Palmas. Com dados reais da Sefin, refazer tudo.
- A faixa de renda é **proxy por setor**, não renda individual. Um contribuinte
  pobre num setor rico fica invisível para a auditoria.
- Imóveis não cadastrados estão **ausentes por construção** — como estariam num
  cadastro real.

---

*Notebook gerado por `notebooks/gerar_eda.py`. Para reproduzir:
`python executar_poc.py` e depois executar este notebook.*
"""),
]


def main() -> None:
    caderno = nbf.v4.new_notebook()
    caderno["cells"] = celulas
    caderno["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    }
    nbf.validate(caderno)
    with open(DESTINO, "w", encoding="utf-8") as arquivo:
        nbf.write(caderno, arquivo)
    print(f"notebook gerado: {DESTINO.name} ({len(celulas)} celulas)")


if __name__ == "__main__":
    main()
