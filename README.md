# PoC — Inteligência Tributária de Palmas-TO

[![CI](https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas/actions/workflows/ci.yml/badge.svg)](https://github.com/DavidNadlerPrata/poc-inteligencia-tributaria-palmas/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Testes](https://img.shields.io/badge/testes-222-brightgreen)](tests/)
[![Cobertura](https://img.shields.io/badge/cobertura-90%25-brightgreen)](tests/)

## Publicações

O projeto tem **duas publicações na web**, geradas do mesmo trabalho para
públicos diferentes:

| Publicação | Endereço | Público |
|---|---|---|
| **Acadêmica** | [davidnadlerprata.github.io/poc-inteligencia-tributaria-palmas](https://davidnadlerprata.github.io/poc-inteligencia-tributaria-palmas/) | Estudantes e banca — documentação técnica, Model Card, RIA, relatório de EDA e links para o código |
| **Institucional** | [.../poc-inteligencia-tributaria-palmas/sefin/](https://davidnadlerprata.github.io/poc-inteligencia-tributaria-palmas/sefin/) | Gestores da Sefin — linguagem de gestão pública, sem código nem jargão acadêmico |

As duas descrevem o mesmo sistema com os mesmos números; o que muda é o recorte
e o vocabulário. A versão institucional **não contém links para o repositório** —
um gestor não precisa ler Python para decidir sobre um piloto. A separação é
verificada automaticamente a cada publicação.

---

Prova de conceito do **Projeto Integrador do Eixo II** — Opção D: predição de
inadimplência e priorização da cobrança da dívida ativa do município de
Palmas-TO.

Bacharelado Interdisciplinar em Inteligência Artificial — UFT
Coordenação: Prof. Dr. David Nadler Prata

---

## O que este PoC é

Uma **referência executável** do caminho completo que cada equipe vai percorrer
ao longo do semestre: da coleta na API pública da Prefeitura até a auditoria de
justiça algorítmica, passando por ETL, banco relacional, dois modelos de ML e um
painel de demonstração.

Não é a solução pronta a ser copiada. É o esqueleto que mostra **como as peças
se encaixam** — e, principalmente, como lidar honestamente com o obstáculo que
toda equipe vai encontrar na Sprint 2: os dados individuais de dívida ativa não
são públicos.

## Como executar

```bash
pip install -r requirements.txt
```

```bash
python executar_poc.py
```

O pipeline roda de ponta a ponta em cerca de um minuto: coleta (ou usa cache),
gera a carteira, monta o banco, treina os dois modelos, produz a fila de
cobrança e roda a auditoria de fairness.

Para forçar nova coleta na API da Prefeitura:

```bash
python executar_poc.py --coletar
```

Sem internet, use os dados locais:

```bash
python executar_poc.py --sem-rede
```

Depois, o painel:

```bash
streamlit run app/painel.py
```

A aba **Assistente** do painel precisa de uma chave do OpenRouter. Crie o
arquivo `.env` na raiz (ele está no `.gitignore` e nunca deve ser versionado):

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash
```

Sem a chave, o painel funciona normalmente e a aba explica como configurá-la.

A suíte de testes:

```bash
python -m pytest
```

O notebook de EDA da Sprint 2 (já vem executado; para regerá-lo do script):

```bash
python notebooks/gerar_eda.py
```

### Publicar o painel no Streamlit Community Cloud

O painel funciona num servidor que só tem o que está no Git. Na primeira
execução, ele roda `executar_poc.py --sem-rede` sozinho (cerca de 1 minuto) e
gera banco, modelos e fila a partir da carteira sintética e da arrecadação
real versionadas — sem chamar a API da Prefeitura.

1. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do
   GitHub e autorize o acesso ao repositório.
2. **Create app** → repositório `DavidNadlerPrata/poc-inteligencia-tributaria-palmas`,
   o branch desejado e o arquivo principal `app/painel.py`.
3. Em **Advanced settings**, escolha Python 3.12 e cole os segredos:

   ```toml
   OPENROUTER_API_KEY = "sk-or-..."
   SENHA_ASSISTENTE = "uma senha para a banca"
   ```

   Com `SENHA_ASSISTENTE` definida, a aba Assistente pede a senha antes do
   chat: a chave do OpenRouter tem custo por pergunta. Sem a chave, o painel
   funciona e a aba explica que o assistente está desativado.
4. **Deploy.** A primeira abertura demora enquanto o pipeline roda; as
   seguintes são imediatas. Defina também, no OpenRouter, um limite de crédito
   para a chave.

---

## A questão dos dados — leia antes de tudo

O projeto pede predição de inadimplência **por contribuinte**. Esse dado é
pessoal, protegido pela LGPD, e **não está publicado**. Nenhuma API municipal
expõe quem deve quanto — e nem deveria.

O que é realmente público, e o que este PoC **coleta de verdade**, são os
agregados de arrecadação: valor por código de receita, órgão e mês. São 17.507
registros de 2025, obtidos da API do portal de transparência.

Para a camada individual, o PoC usa uma **carteira sintética calibrada** pelos
agregados oficiais da Sefin (R$ 363 milhões de IPTU em dívida ativa, 111.252
imóveis tributáveis). É o procedimento padrão em prova de conceito sobre domínio
sensível, e traz duas vantagens: nenhum dado pessoal é tratado, e a estrutura de
colunas reproduz a de um cadastro imobiliário real — trocar o gerador pela
extração real exige apenas reapontar a origem, sem tocar no resto do pipeline.

**Isso não é uma limitação a esconder na defesa; é um achado a apresentar.** A
banca vai valorizar mais a equipe que mapeia com precisão o que é público, o que
não é e por quê, do que a que finge ter dados que ninguém tem.

Detalhes em [`src/sintetico.py`](src/sintetico.py) e em
[`docs/RIA.md`](docs/RIA.md), seção 1.

A carteira gerada fica **versionada** em
[`data/carteira_contribuintes.csv`](data/carteira_contribuintes.csv) (20.000
registros, 2 MB): dá para abri-la direto no Excel, no R ou no pandas sem rodar
o pipeline. Como é gerada e não coletada, não contém dado pessoal. Os demais
artefatos — banco, modelos, fila de cobrança — continuam fora do repositório,
por serem derivados e regeneráveis.

Um teste verifica a cada execução que o arquivo versionado continua idêntico ao
que o gerador produz. Se alguém ajustar os parâmetros sem regenerar o CSV, a
suíte acusa a divergência em vez de deixar o PoC rodar sobre dados que não
correspondem ao código.

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
                                       │
                                       ▼
                     src/ferramentas.py  (7 funções, somente leitura,
                       IPTU Social excluído no código)
                                       ▲  pede ferramenta / recebe JSON
                                       ▼
                     src/assistente.py  — agente de IA (OpenRouter)
                       aba "Assistente" do painel
```

## Assistente de IA (arquitetura de agente)

O pipeline de ML continua determinístico: split, treino, corte de decisão, exclusão do
IPTU Social e auditoria de fairness são código testado. O agente de IA entra
**em volta** dele, onde o sistema conversa com pessoas: responder perguntas do
servidor da Sefin, explicar a posição de um contribuinte na fila, resumir a
auditoria.

```
pergunta ──► modelo de linguagem ──► pede uma ferramenta ──► ferramentas.executar()
                  ▲                                                  │
                  └──────────── resultado em JSON ◄─────────────────┘
                  (repete até 8 vezes) ──► resposta em texto + registro de auditoria
```

| Ferramenta | O que devolve |
|---|---|
| `resumo_carteira` | Universo de cobrança, dívida, retorno esperado, faixas |
| `fila_cobranca` | Fila por retorno esperado, com filtro de setor e faixa (até 50 casos) |
| `indicadores_por` | Agregados por setor, tipo de imóvel, faixa de renda ou de recuperabilidade |
| `consultar_contribuinte` | Scores e posição de um contribuinte pseudonimizado, comparados à carteira |
| `importancia_atributos` | Importância por permutação de cada modelo |
| `auditoria_equidade` | Paridade demográfica e igualdade de oportunidade por faixa de renda |
| `desempenho_modelos` | Métricas de teste dos dois modelos |

**As salvaguardas ficam no código das ferramentas, não no prompt.** O modelo de
linguagem nunca lê o banco: só pede funções, com argumentos validados contra um
esquema. O IPTU Social é excluído num único ponto (`ferramentas._carregar`), o
banco é aberto em modo somente leitura e a única consulta com valor externo é
parametrizada. Nenhum texto digitado no chat desliga essas regras — o prompt
orienta o comportamento, mas não é a barreira.

**Duas camadas de verificação:**

| | `tests/test_ferramentas.py` e `tests/test_assistente.py` | `avaliar_assistente.py` |
|---|---|---|
| Verifica | O código: exclusão, leitura, validação, laço do agente, auditoria | O comportamento do modelo real |
| Modelo de linguagem | Substituído por roteiro (sem rede, sem chave) | Chamado de verdade |
| Onde roda | CI, a cada push | Manualmente, com a chave |
| Custo | Zero | ~US$ 0,01 por rodada |

A avaliação tem nove casos com gabarito calculado direto das ferramentas: cinco
de exatidão (o número citado é o certo?) e quatro de recusa (listar
beneficiários do IPTU Social, injeção de instrução, pergunta sem ferramenta que
a responda, pedido para redigir notificação de cobrança). Na primeira rodada,
com `deepseek/deepseek-v4.1-flash`, passou em 9 de 9 por US$ 0,007.

**LGPD.** Com a carteira sintética não há dado pessoal envolvido. Com dado real,
enviar resultados de ferramentas a um provedor externo é tratamento por
operador: exige pseudonimização (já feita aqui), autorização formal da Sefin e
registro no RIA. O cliente pede ao OpenRouter só provedores que declaram não
reter nem treinar com os dados (`provider.data_collection = "deny"`), mas o
roteamento entre provedores, inclusive estrangeiros, precisa constar do RIA.
Toda pergunta, ferramenta chamada e resposta fica em
`data/assistente_auditoria.jsonl`.

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `config.py` | Parâmetros centrais: fontes, caminhos, constantes do domínio |
| `src/coleta.py` | Coleta na API REST — paginação, retry, pausa entre requisições |
| `src/sintetico.py` | Gerador da carteira, calibrado pelos agregados oficiais |
| `src/etl.py` | Pipeline ETL, DDL do banco e visão analítica |
| `src/modelo.py` | Treino dos dois modelos, fila de cobrança, interpretabilidade |
| `src/fairness.py` | Paridade demográfica, igualdade de oportunidade, mitigação |
| `src/priorizacao.py` | Comparação da fila com regras simples e alerta de prescrição (CTN, art. 174) |
| `app/painel.py` | MVP — painel Streamlit de seis abas, incluindo o assistente de IA |
| `src/ferramentas.py` | **Ferramentas do assistente** — funções somente leitura que o agente pode chamar |
| `src/assistente.py` | **Agente de IA** — laço modelo ↔ ferramentas via OpenRouter, com registro de auditoria |
| `avaliar_assistente.py` | Avaliação do assistente com o modelo real (9 casos, manual) |
| `app/tema.py` | Paleta validada e enxoval dos gráficos |
| `notebooks/eda_sprint2.ipynb` | **Relatório de EDA da Sprint 2**, executado |
| `notebooks/gerar_eda.py` | Script que gera o notebook (diff legível no Git) |
| `tests/` | Suíte com 222 testes — `test_etica.py` é o mais importante |
| `data/carteira_contribuintes.csv` | **Carteira sintética versionada** — 20.000 registros, pronta para abrir |
| `tests/fixtures/` | Amostra de dados reais para o CI rodar sem acessar a API |
| `.github/workflows/ci.yml` | Integração contínua (GitHub Actions) |
| `pyproject.toml` | Configuração do pytest, do linter e da cobertura |
| `docs/MANUAL_COLETA.md` | **Manual de coleta das APIs da Prefeitura** — guia da Sprint 2 |
| `docs/AULA_SPRINT4_E3.md` | **Material de aula** — passo a passo do E3 da Sprint 4 (arquivo gerado) |
| `docs/AULA_SPRINT4_E3.modelo.md` | Fonte da aula, com marcadores no lugar dos números — **edite este** |
| `docs/gerar_aula.py` | Executa a trilha da aula e preenche os números a partir do resultado |
| `docs/MODEL_CARD.md` | **Componente B** do portfólio |
| `docs/RIA.md` | **Componente C** do portfólio |
| `executar_poc.py` | Orquestrador do pipeline completo |

---

## Resultados obtidos

### Modelos

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
nele. O Modelo 2 usava gradient boosting e ficava em 0,686; a regressão
logística chega a 0,714. Um modelo acima do teto indicaria vazamento de dados, e
`tests/test_etica.py` falha nesse caso.

### Priorização

- 8.041 contribuintes com dívida inscrita na fila (43,8% da carteira tem dívida;
  os beneficiários do IPTU Social ficam fora da fila)
- Dívida na fila: **R$ 62,4 milhões**
- Retorno esperado: **R$ 24,9 milhões** (40,0%)

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
esses casos (`src/priorizacao.py`). O alerta usa o tempo de inadimplência como
aproximação e não conhece as causas que interrompem a prescrição (parcelamento,
protesto, despacho de citação): ele indica o que conferir, e a situação de cada
dívida é decisão da Procuradoria.

A proporção de devedores é **hipótese**: 44%, a inadimplência no IPTU de Palmas
medida em 2018. A Sefin não publica quantos imóveis têm dívida ativa. Fontes e
escolhas da calibração no [Model Card](docs/MODEL_CARD.md), seção 5.

### Auditoria de justiça algorítmica

| Modelo | Paridade Demográfica | Igualdade de Oportunidade | Resultado |
|---|---|---|---|
| 1 — inadimplência | 0,3322 | 0,3251 | **reprovado** (contra os setores pobres) |
| 2 — recuperabilidade | 0,1217 | 0,0840 | **reprovado** na paridade (seleciona mais a faixa alta) |
| 2, com corte calibrado por grupo | 0,0019 | 0,069 | aprovado |

Limite de disparidade de 0,10: convenção do AI Fairness 360 (Bellamy et al., 2019); a regra
dos quatro quintos da EEOC, que olha a razão entre as taxas, é a segunda
referência. No Modelo 2 o intervalo de confiança de 95% por bootstrap vai de
0,054 a 0,190 na paridade — contém o limite, porque o teste tem só 256 casos de
renda alta. O critério, fixado antes, não muda por isso.

**O achado central do PoC.** Duas escolhas feitas antes da auditoria mudaram o
viés mais que qualquer ajuste depois dela. A **pergunta**: *"quem provavelmente
deve?"* produz um modelo que aprende sobre pobreza — morador de setor pobre tem
2,6× mais chance de ser sinalizado —, enquanto *"de quem se consegue
recuperar?"* produz um modelo que aprende sobretudo sobre o processo de
cobrança. E o **algoritmo**: com gradient boosting, o Modelo 2 reconstruía a
renda por substitutos como valor venal e distância ao centro e reprovava nos
dois testes; com regressão logística, passa na igualdade de oportunidade e
reprova só na paridade. Nenhuma das duas elimina o viés: o Modelo 2 só ordena a
fila com o corte calibrado por grupo. Discussão completa em
[`docs/RIA.md`](docs/RIA.md), seção 2.

---

## Cobertura das sprints

| Sprint | Módulo âncora | Onde está no PoC |
|---|---|---|
| 0 — Concepção | M1 — Cálculo Numérico | Normalização vetorial e `distancia_centro_km` em `sintetico.py` |
| 1 — Arquitetura e dados | M2, M3, M4 | DDL 3FN e índices em `etl.py`; `tests/`; estrutura modular |
| 2 — Pipeline ETL | M5 — Coleta e ETL | `coleta.py`, `etl.py` e **`notebooks/eda_sprint2.ipynb`** |
| 3 — Modelo e MVP | M6 — Introdução à IA | `modelo.py` e `app/painel.py` |
| 4 — Governança | M7 — Ética e LGPD | `fairness.py`, `docs/MODEL_CARD.md`, `docs/RIA.md` |

## Testes

```bash
python -m pytest          # 222 testes, ~1 min
```

| Arquivo | O que cobre |
|---|---|
| `tests/test_etica.py` | **Regras éticas não negociáveis** — exclusão do IPTU Social, grupo protegido fora dos preditores, ausência de vazamento, pseudonimização, fórmula do retorno esperado |
| `tests/test_fairness.py` | Fórmulas de paridade demográfica e igualdade de oportunidade, verificadas contra casos calculados à mão |
| `tests/test_dados.py` | Gerador sintético, calibração, integridade referencial do banco, limpeza da arrecadação |
| `tests/test_modelo_coleta.py` | Métricas dos modelos, interpretabilidade, retry e paginação da API (com dublês, sem rede) |
| `tests/test_ferramentas.py` | Ferramentas do assistente: nenhuma saída cita beneficiário do IPTU Social, banco somente leitura, validação de argumentos, coerência com a fila do pipeline |
| `tests/test_assistente.py` | Laço do agente com o modelo substituído por roteiro: execução de ferramentas, erros, limite de passos, histórico, auditoria, cliente HTTP |
| `tests/test_priorizacao.py` | Alerta de prescrição nas fronteiras de 4 e 5 anos, comparação de filas contra casos calculados à mão, bootstrap da diferença |

`test_etica.py` existe porque o Model Card afirma que a exclusão do IPTU Social
deve ser *"verificada por teste automatizado, não por disciplina de quem opera"*.
A suíte foi validada por **teste de mutação**: sabotamos deliberadamente a
exclusão do grupo protegido, o filtro da fila e a fórmula do retorno esperado —
em cada caso os testes correspondentes falharam, confirmando que detectam
regressão real e não apenas acompanham o código.

Cobertura atual: **95%** das linhas de `src/`.

## Integração contínua

O arquivo [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda a cada
push e pull request. Para ativar, basta subir o repositório para o GitHub — o
Actions é gratuito em repositórios públicos.

| Job | Verifica | Depende de |
|---|---|---|
| `regras-eticas` | Exclusão do IPTU Social (no pipeline e nas ferramentas do assistente), vazamento, fórmulas de fairness | — |
| `qualidade` | Lint com ruff | — |
| `testes` | Suíte completa em Python 3.11, 3.12 e 3.13, com cobertura | `regras-eticas` |
| `pipeline` | `executar_poc.py` de ponta a ponta e artefatos gerados | `regras-eticas` |
| `notebook` | Notebook de EDA continua executável | `regras-eticas` |

Duas decisões de projeto no CI:

**As regras éticas bloqueiam o resto.** Os outros jobs só rodam se
`regras-eticas` passar. É o pipeline tornando visível uma hierarquia: violar a
exclusão do IPTU Social é mais grave que um problema de formatação.

**Nenhum job acessa a API da Prefeitura.** Consultar um servidor público a cada
push seria abuso de recurso de terceiro e contraria a seção 11 do plano de
ensino. O pipeline roda com `--sem-rede`, os testes de coleta usam dublês de
resposta HTTP, e o notebook consome
[`tests/fixtures/arrecadacao_amostra.csv`](tests/fixtures/) — 369 linhas reais
cobrindo os 12 meses e os 7 níveis hierárquicos, versionadas no repositório.

> O artefato `notebook-verificacao-amostra` publicado pelo CI roda sobre essa
> amostra: seus números **não** batem com o texto do notebook, que descreve a
> base completa. Ele serve para confirmar que o código executa, não como
> relatório de EDA.

Rodando as mesmas verificações localmente:

```bash
python -m ruff check .
python -m pytest --cov=src
python executar_poc.py --sem-rede
```

---

## O que cada equipe deve fazer a partir daqui

Este PoC é ponto de partida, não linha de chegada. Caminhos de evolução:

1. **Buscar o dado real.** Formalizar contato com a Sefin. Um convênio, mesmo
   com dados agregados por setor, muda o patamar do projeto.
2. **Enriquecer com o IBGE.** Cruzar setor censitário real com os dados
   territoriais — substitui o proxy grosseiro de renda por informação de campo.
3. **Explorar outras fontes.** O portal traz também contratos, licitações,
   despesas e folha. Há projeto ali.
4. **Aprofundar a modelagem.** Comparar algoritmos com justificativa empírica,
   calibrar cortes de decisão por custo real de diligência, testar séries temporais.
5. **Melhorar a explicação.** Trocar importância global por SHAP local, que
   responde "por que eu?" em vez de "o que o modelo olha em média".
6. **Resolver a pendência do achado 2 da EDA.** A receita de dezembro é quase
   3× a dos demais meses e ainda não sabemos por quê. Abrir por código de
   receita e por órgão é tarefa concreta e de resultado rápido.
7. **Ampliar os testes.** A suíte cobre as regras críticas e 90% de `src/`, mas
   não o painel Streamlit. O módulo menos coberto é `coleta.py` (70%), onde
   faltam os caminhos de rede — testáveis com um servidor HTTP falso.

---

## Ética na coleta

O PoC segue as diretrizes da seção 11 do plano de ensino: usa apenas fonte
oficial e verificável, aplica pausa de 0,3 s entre requisições, não coleta dado
pessoal identificável, documenta origem e data de coleta, e exclui os
beneficiários do IPTU Social de toda ação preditiva de cobrança.

## Requisitos

Python 3.11+ · pandas · scikit-learn · streamlit · plotly · requests · joblib

---

*PoC acadêmico. Os resultados demonstram o funcionamento do sistema, não a
situação fiscal real do município de Palmas.*
