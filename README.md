# PoC — Inteligência Tributária de Palmas-TO

<!-- Troque USUARIO/REPOSITORIO pelo caminho do repositório da sua equipe. -->
[![CI](https://github.com/USUARIO/REPOSITORIO/actions/workflows/ci.yml/badge.svg)](https://github.com/USUARIO/REPOSITORIO/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Testes](https://img.shields.io/badge/testes-97-brightgreen)](tests/)
[![Cobertura](https://img.shields.io/badge/cobertura-90%25-brightgreen)](tests/)

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

A suíte de testes:

```bash
python -m pytest
```

O notebook de EDA da Sprint 2 (já vem executado; para regerá-lo do script):

```bash
python notebooks/gerar_eda.py
```

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

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `config.py` | Parâmetros centrais: fontes, caminhos, constantes do domínio |
| `src/coleta.py` | Coleta na API REST — paginação, retry, pausa entre requisições |
| `src/sintetico.py` | Gerador da carteira, calibrado pelos agregados oficiais |
| `src/etl.py` | Pipeline ETL, DDL do banco e visão analítica |
| `src/modelo.py` | Treino dos dois modelos, fila de cobrança, interpretabilidade |
| `src/fairness.py` | Paridade demográfica, igualdade de oportunidade, mitigação |
| `app/painel.py` | MVP — painel Streamlit de cinco abas |
| `app/tema.py` | Paleta validada e enxoval dos gráficos |
| `notebooks/eda_sprint2.ipynb` | **Relatório de EDA da Sprint 2**, executado |
| `notebooks/gerar_eda.py` | Script que gera o notebook (diff legível no Git) |
| `tests/` | Suíte com 97 testes — `test_etica.py` é o mais importante |
| `tests/fixtures/` | Amostra de dados reais para o CI rodar sem acessar a API |
| `.github/workflows/ci.yml` | Integração contínua (GitHub Actions) |
| `pyproject.toml` | Configuração do pytest, do linter e da cobertura |
| `docs/MODEL_CARD.md` | **Componente B** do portfólio |
| `docs/RIA.md` | **Componente C** do portfólio |
| `executar_poc.py` | Orquestrador do pipeline completo |

---

## Resultados obtidos

### Modelos

| | Modelo 1 — inadimplência | Modelo 2 — recuperabilidade |
|---|---|---|
| Acurácia | 0,652 | 0,620 |
| Precisão | 0,664 | 0,616 |
| Recall | 0,634 | 0,698 |
| F1 | 0,649 | 0,654 |
| ROC-AUC | 0,702 | 0,666 |

Desempenho moderado é o resultado honesto: o processo gerador embute ruído
deliberado. Métricas perto de 1,0 num PoC assim indicariam vazamento de dados.

### Priorização

- 15.361 contribuintes com dívida inscrita
- Dívida na carteira: **R$ 62,8 milhões**
- Retorno esperado: **R$ 29,5 milhões** (47,0%)
- Os **20% melhores casos concentram 50,5%** do retorno esperado

### Auditoria de justiça algorítmica

| Modelo | Paridade Demográfica | Igualdade de Oportunidade | Resultado |
|---|---|---|---|
| 1 — inadimplência | 0,4745 | 0,4757 | **reprovado** |
| 2 — recuperabilidade | 0,0475 | 0,0412 | aprovado |

Mitigação por limiar calibrado por grupo: disparidade **0,0475 → 0,0006**.

**O achado central do PoC.** Dois modelos, mesmos dados, mesmo algoritmo,
comportamentos éticos opostos. Perguntar *"quem provavelmente deve?"* produz um
modelo que aprende sobre pobreza — morador de setor pobre tem 3,3× mais chance
de ser sinalizado. Perguntar *"de quem se consegue recuperar?"* produz um modelo
que aprende sobre processo de cobrança, e passa nos dois testes. **A escolha da
variável-alvo é uma decisão ética, tomada antes da primeira linha de código de
modelagem.** Discussão completa em [`docs/RIA.md`](docs/RIA.md), seção 2.

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
python -m pytest          # 97 testes, ~50 s
```

| Arquivo | O que cobre |
|---|---|
| `tests/test_etica.py` | **Regras éticas não negociáveis** — exclusão do IPTU Social, grupo protegido fora dos preditores, ausência de vazamento, pseudonimização, fórmula do retorno esperado |
| `tests/test_fairness.py` | Fórmulas de paridade demográfica e igualdade de oportunidade, verificadas contra casos calculados à mão |
| `tests/test_dados.py` | Gerador sintético, calibração, integridade referencial do banco, limpeza da arrecadação |
| `tests/test_modelo_coleta.py` | Métricas dos modelos, interpretabilidade, retry e paginação da API (com dublês, sem rede) |

`test_etica.py` existe porque o Model Card afirma que a exclusão do IPTU Social
deve ser *"verificada por teste automatizado, não por disciplina de quem opera"*.
A suíte foi validada por **teste de mutação**: sabotamos deliberadamente a
exclusão do grupo protegido, o filtro da fila e a fórmula do retorno esperado —
em cada caso os testes correspondentes falharam, confirmando que detectam
regressão real e não apenas acompanham o código.

Cobertura atual: **90%** das linhas de `src/`.

## Integração contínua

O arquivo [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda a cada
push e pull request. Para ativar, basta subir o repositório para o GitHub — o
Actions é gratuito em repositórios públicos.

| Job | Verifica | Depende de |
|---|---|---|
| `regras-eticas` | Exclusão do IPTU Social, vazamento, fórmulas de fairness | — |
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
   calibrar limiares por custo real de diligência, testar séries temporais.
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
