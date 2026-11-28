# Inteligência Tributária de Palmas-TO

<p class="subtitulo">Predição de inadimplência e priorização da dívida ativa — prova de conceito do Projeto Integrador do Eixo II.</p>

<p class="creditos">Bacharelado Interdisciplinar em Inteligência Artificial — Universidade Federal do Tocantins<br>Coordenação: Prof. Dr. David Nadler Prata</p>

<div class="botoes">
<a class="botao botao-primario" href="https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas">Ver o código no GitHub</a>
<a class="botao botao-secundario" href="manual-coleta.html">Manual de coleta</a>
<a class="botao botao-secundario" href="aula-sprint4-e3.html">Aula: Sprint 4</a>
<a class="botao botao-secundario" href="eda.html">Relatório de EDA</a>
<a class="botao botao-secundario" href="model-card.html">Model Card</a>
<a class="botao botao-secundario" href="ria.html">Relatório de Impacto</a>
</div>

Palmas acumula cerca de **R$ 894 milhões** em dívida ativa, dos quais R$ 363
milhões de IPTU. Com 111.252 imóveis tributáveis, o município enfrenta um
problema de alocação: onde concentrar o esforço de cobrança para recuperar mais
com a mesma equipe.

Este PoC é uma **referência executável** do caminho completo que cada equipe vai
percorrer ao longo do semestre — da coleta na API pública da Prefeitura até a
auditoria de justiça algorítmica, passando por ETL, banco relacional, dois
modelos de aprendizado de máquina e um painel de demonstração.

Não é a solução pronta a ser copiada. É o esqueleto que mostra como as peças se
encaixam, e como lidar honestamente com o obstáculo que toda equipe vai
encontrar na Sprint 2.

---

## O achado central

<div class="destaque">
<h3>A pergunta e o algoritmo decidem o viés antes da auditoria</h3>

<p>Treinamos dois classificadores sobre a mesma base e os mesmos atributos. O viés
de cada um dependeu de duas escolhas feitas antes de qualquer auditoria: a
<strong>pergunta</strong> e o <strong>algoritmo</strong>.</p>

<p>Perguntar <em>"quem provavelmente vai dever?"</em> produz um modelo que aprende sobre
pobreza: morador de setor de renda baixa tem <strong>2,6 vezes</strong> mais chance de ser
sinalizado. Perguntar <em>"de quem se consegue recuperar?"</em> produz um modelo que
aprende sobretudo sobre o processo de cobrança — o tempo desde a inscrição da
dívida é, de longe, o atributo mais importante.</p>

<p>Com gradient boosting, esse segundo modelo ainda reconstruía a renda por
substitutos como valor venal e distância ao centro, e reprovava nos dois testes.
Com regressão logística, os substitutos perderam peso: ele passa na igualdade de
oportunidade e reprova só na paridade, selecionando mais a faixa de renda alta.</p>

<p><strong>Pergunta e algoritmo reduzem o viés, mas não o eliminam.</strong> O que torna
o segundo modelo utilizável é a combinação deles com uma mitigação explícita e
auditável.</p>
</div>

| Modelo | Paridade Demográfica | Igualdade de Oportunidade | Resultado |
|---|---|---|---|
| 1 — inadimplência | 0,3322 | 0,3251 | <span class="selo selo-reprovado">reprovado</span> |
| 2 — recuperabilidade | 0,1217 | 0,0840 | <span class="selo selo-reprovado">reprovado</span> |
| 2, com corte calibrado por grupo | 0,0019 | 0,069 | <span class="selo selo-aprovado">aprovado</span> |

O limite de disparidade adotado é 0,10 de diferença, convenção do AI Fairness 360 (Bellamy et
al., 2019). Com só 256 casos de renda alta no teste, o intervalo de confiança
de 95% da paridade do Modelo 2 vai de 0,054 a 0,190 — contém o limite, mas o
critério, fixado antes da auditoria, não muda por isso. A consequência prática é direta: **apenas o Modelo 2 ordena a fila de cobrança, e
só com o corte calibrado por grupo**. O Modelo 1 fica restrito a uso
diagnóstico — dimensionar o problema, planejar educação fiscal, subsidiar
política pública.

A discussão completa, incluindo a impossibilidade matemática de satisfazer
paridade e calibração ao mesmo tempo, está no
[Relatório de Impacto Algorítmico](ria.html#seção-2--análise-de-justiça-algorítmica).

---

## Resultados

<div class="cartoes">
<div class="cartao"><div class="valor">17.507</div><div class="rotulo">registros reais coletados da API da Prefeitura</div></div>
<div class="cartao"><div class="valor">51,7%</div><div class="rotulo">do retorno esperado concentrado nos 20% melhores casos</div></div>
<div class="cartao"><div class="valor">222</div><div class="rotulo">testes automatizados, 95% de cobertura</div></div>
<div class="cartao"><div class="valor">0,0019</div><div class="rotulo">disparidade após mitigação (era 0,1217)</div></div>
</div>

### Desempenho dos modelos

| | Modelo 1 — inadimplência | Modelo 2 — recuperabilidade |
|---|---|---|
| Algoritmo | gradient boosting | regressão logística |
| Acurácia | 0,768 | 0,654 |
| Precisão | 0,756 | 0,602 |
| Recall | 0,685 | 0,571 |
| F1 | 0,719 | 0,586 |
| ROC-AUC | 0,804 | 0,714 |
| Teto do ROC-AUC nesta carteira | 0,804 | 0,722 |

O processo gerador embute ruído deliberado, e por isso há um teto: o ROC-AUC de
um oráculo que conhece a fórmula do gerador. Os dois modelos estão praticamente
nele. Um valor acima do teto seria impossível de forma legítima e indicaria
vazamento de dados, não qualidade.

A carteira é sintética e calibrada por números publicados. A proporção de
imóveis com dívida (44%) é uma **hipótese** baseada na inadimplência medida em
2018, porque a Sefin não publica esse número — detalhes no
[Model Card](model-card.html#5-dados-de-treinamento).

### Priorização da cobrança

A fila é ordenada por **retorno esperado** — o produto entre o valor da dívida e
a probabilidade de recuperação. Ordenar apenas pela probabilidade privilegiaria
dívidas pequenas e fáceis; apenas pelo valor, dívidas grandes e incobráveis. O
produto equilibra os dois.

**A fila do modelo é melhor que uma regra simples?** Nas dívidas do conjunto
de teste, trabalhar os 20% primeiros de cada fila alcança esta fração do valor
**de fato recuperado**:

| Fila ordenada por… | 20% primeiros | 50% primeiros |
|---|---|---|
| Modelo 2 (dívida × probabilidade) | **47,4%** | 81,3% |
| Maiores dívidas primeiro | 43,8% | 75,0% |
| Mais recentes primeiro | 31,5% | 67,1% |
| Só a probabilidade do modelo | 24,7% | 61,4% |
| Ordem aleatória | 20,0% | 50,0% |

O modelo ganha da regra "maiores dívidas primeiro" por 3,7 pontos percentuais
(IC 95% de 0,5 a 7,2): a diferença é real, mas pequena perto da que separa as
duas da ordem aleatória. Quase todo o ganho vem de ordenar pelo valor.

**Prescrição.** A fila ordena por retorno esperado e não considera o prazo de
cinco anos da ação de cobrança (CTN, art. 174). Com isso, 826 dívidas
(R$ 6,7 mi) que prescrevem em até 12 meses ficam espalhadas pela fila — só 84
nos 20% primeiros, com posição mediana em 61% da fila —, e outras 1.536
(R$ 12,7 mi), com 5 anos ou mais, ficam no fim. O painel e o assistente marcam
esses casos. O alerta usa o tempo de inadimplência como
aproximação e não conhece as causas que interrompem a prescrição (parcelamento,
protesto, despacho de citação): ele indica o que conferir, e a situação de cada
dívida é decisão da Procuradoria.

---

## A questão dos dados

<div class="aviso">
<p><strong>O projeto pede predição por contribuinte. Esse dado não é público — e nem deveria ser.</strong></p>

<p>O registro individual de dívida ativa é dado pessoal, protegido pela LGPD, e só
pode ser acessado mediante convênio formal com a Sefin. Nenhuma API municipal
expõe quem deve quanto.</p>
</div>

O que é realmente público, e o que este PoC **coleta de verdade**, são os
agregados de arrecadação: valor por código de receita, órgão e mês — 17.507
registros de 2025, obtidos da API do portal de transparência.

Para a camada individual, o PoC usa uma **carteira sintética calibrada** pelos
agregados oficiais da Sefin. É o procedimento padrão em prova de conceito sobre
domínio sensível, e traz duas vantagens: nenhum dado pessoal é tratado, e a
estrutura de colunas reproduz a de um cadastro imobiliário real — trocar o
gerador pela extração real exige apenas reapontar a origem, sem tocar no resto
do pipeline.

Isso não é uma limitação a esconder na defesa; é um achado a apresentar. A banca
valoriza mais a equipe que mapeia com precisão o que é público, o que não é e
por quê, do que a que finge ter dados que ninguém tem.

---

## Arquitetura

```
                 API REST da Prefeitura            gerador calibrado
              (sgreceitas/listar — REAL)          (carteira SINTÉTICA)
                          │                                │
                          └────────────┬───────────────────┘
                                       ▼
                              ETL  (src/etl.py)
                       limpeza · normalização 3FN · carga
                                       │
                                       ▼
                        SQLite  inteligencia_tributaria.db
                setor_urbano ─< imovel ─< divida_ativa
                                  └─< historico_cobranca
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        Modelo 1: inadimplência              Modelo 2: recuperabilidade
         (uso diagnóstico apenas)           (ordena a fila de cobrança)
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       ▼
                    auditoria de fairness · painel Streamlit
```

---

## Cobertura das sprints

| Sprint | Módulo âncora | Onde está no PoC |
|---|---|---|
| 0 — Concepção | M1 — Cálculo Numérico | Normalização vetorial e distância ao centro urbano |
| 1 — Arquitetura e dados | M2, M3, M4 | DDL em 3FN, índices, estrutura modular do repositório |
| 2 — Pipeline ETL | M5 — Coleta e ETL | [Manual de coleta](manual-coleta.html), coleta na API real e [relatório de EDA](eda.html) |
| 3 — Modelo e MVP | M6 — Introdução à IA | [Material de aula do E3](aula-sprint4-e3.html), dois modelos e painel Streamlit |
| 4 — Governança | M7 — Ética e LGPD | [Model Card](model-card.html) e [RIA](ria.html) |

---

## Como executar

O painel é interativo e precisa de um servidor Python — por isso não roda nesta
página, que é estática. Para vê-lo funcionando:

```bash
git clone https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas.git
cd poc-inteligencia-tributaria-palmas
pip install -r requirements.txt
python executar_poc.py
streamlit run app/painel.py
```

O pipeline completo roda em cerca de um minuto: coleta os dados, monta o banco,
treina os dois modelos, gera a fila de cobrança e executa a auditoria de
fairness.

---

## Ética na coleta

O PoC segue as diretrizes da seção 11 do plano de ensino: usa apenas fonte
oficial e verificável, aplica pausa entre requisições, não coleta dado pessoal
identificável, documenta origem e data de coleta, e exclui os beneficiários do
IPTU Social — idosos, aposentados, pensionistas e pessoas com deficiência de
baixa renda — de toda ação preditiva de cobrança.

Essa exclusão não depende da disciplina de quem opera: é verificada por
[teste automatizado](https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas/blob/main/tests/test_etica.py)
que bloqueia a integração contínua caso seja violada.
