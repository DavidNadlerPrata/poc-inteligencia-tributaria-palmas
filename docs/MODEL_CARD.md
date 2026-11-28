# Model Card — Sistema de Inteligência Tributária de Palmas-TO

Documento de transparência algorítmica no formato de Mitchell et al. (2019),
correspondente ao **Componente B** do portfólio do Projeto Integrador.

> **Aviso de escopo.** Este é um PoC acadêmico. Os modelos foram treinados sobre
> uma carteira **sintética** calibrada por agregados oficiais, porque o registro
> individual de dívida ativa não é público. Os números abaixo descrevem o
> comportamento do sistema, não a situação fiscal real de Palmas.

---

## 1. Detalhes do modelo

O sistema é composto por **dois modelos** que respondem a perguntas diferentes.

| | Modelo 1 | Modelo 2 |
|---|---|---|
| **Nome** | Classificador de inadimplência | Scoring de recuperabilidade |
| **Pergunta** | O contribuinte ficará inadimplente no próximo exercício? | Uma dívida já inscrita será recuperada em 12 meses? |
| **Tipo** | Classificação binária | Classificação binária (usada como score contínuo) |
| **Algoritmo** | `HistGradientBoostingClassifier` | `HistGradientBoostingClassifier` |
| **Framework** | scikit-learn 1.9 | scikit-learn 1.9 |
| **Hiperparâmetros** | `max_iter=250`, `learning_rate=0.08`, `max_depth=6` | idem |
| **Universo de treino** | 18.680 imóveis (após exclusão do IPTU Social) | 8.041 imóveis com dívida inscrita |
| **Versão** | 0.1.0 (PoC) | 0.1.0 (PoC) |
| **Licença** | Acadêmica — uso restrito a ensino e pesquisa | idem |

**Por que gradient boosting?** Os atributos misturam variáveis numéricas de
escalas muito diferentes (reais, dias, contagens) com categóricas de baixa
cardinalidade, e as relações são não lineares — o efeito do tempo de
inadimplência sobre a recuperação satura. Árvores impulsionadas lidam com isso
sem exigir normalização, toleram outliers de valor venal e entregam importância
de atributos diretamente, o que sustenta o direito à explicação. Regressão
logística foi considerada pela interpretabilidade, mas perdeu poder preditivo
nas interações; redes neurais foram descartadas por opacidade desnecessária num
volume de dados desta ordem.

---

## 2. Uso pretendido

**Uso primário.** Ordenar a fila de trabalho da cobrança administrativa da
dívida ativa, para que a equipe da Sefin concentre esforço onde há maior
retorno esperado (`valor da dívida × probabilidade de recuperação`).

**Usuários previstos.** Servidores da Secretaria Municipal de Fazenda com
atribuição de cobrança, sob supervisão da Procuradoria.

**Fora do escopo — usos expressamente não recomendados:**

- Decidir **automaticamente** qualquer ato de cobrança, protesto ou execução
  fiscal. O sistema ordena; a decisão é do servidor.
- Negar parcelamento, benefício fiscal ou certidão com base no score.
- Definir intensidade de fiscalização sobre pessoas físicas identificadas.
- Qualquer uso sobre beneficiários do IPTU Social, que são excluídos por
  construção.
- Transferir o modelo para outro município sem novo treino e nova auditoria.

---

## 3. Fatores relevantes

**Grupos avaliados.** A auditoria usa como grupo protegido a **faixa de renda
predominante do setor urbano** (baixa, média, alta) — um proxy do setor
censitário do IBGE. É um proxy, não a renda individual do contribuinte, e essa
limitação é relevante: um contribuinte de baixa renda num setor rico fica
invisível para a auditoria.

**Fatores de ambiente.** O desempenho depende da qualidade do cadastro
imobiliário. Áreas com cadastro desatualizado — justamente as de ocupação mais
recente e menor renda — tendem a produzir predições piores, o que agrava a
disparidade documentada na seção 5.

**Decisão de projeto.** A faixa de renda **não é atributo preditivo**. Ela entra
apenas na auditoria. Isso não elimina o viés (setor urbano e valor venal são
correlacionados com renda), mas impede a discriminação direta e explícita.

---

## 4. Métricas de avaliação

Conjunto de teste: 25% dos dados, separação estratificada, `random_state=42`.

### Modelo 1 — inadimplência (n = 4.670)

| Métrica | Valor |
|---|---|
| Acurácia | 0,768 |
| Precisão | 0,756 |
| Recall | 0,685 |
| F1-score | 0,719 |
| ROC-AUC | 0,804 |

Matriz de confusão `[[VN, FP], [FN, VP]]` = `[[2200, 447], [638, 1385]]`

### Modelo 2 — recuperabilidade (n = 2.011)

| Métrica | Valor |
|---|---|
| Acurácia | 0,637 |
| Precisão | 0,583 |
| Recall | 0,540 |
| F1-score | 0,561 |
| ROC-AUC | 0,686 |

Matriz de confusão `[[VN, FP], [FN, VP]]` = `[[815, 333], [397, 466]]`

**Leitura honesta destes números.** ROC-AUC de 0,80 (Modelo 1) e 0,69
(Modelo 2): os dois são claramente melhores que o acaso, e o Modelo 2 — o que
ordena a fila — ainda erra com frequência.
Isso é esperado e desejável num PoC cujo processo gerador embute ruído
deliberado. Métricas próximas de 1,0 aqui indicariam vazamento de dados, não
qualidade. Em produção, com histórico real de pagamentos, espera-se desempenho
superior — mas a decisão de tratar o resultado como **fila de trabalho**, e não
como veredito, permanece válida em qualquer nível de acurácia.

**Métrica que mais importa.** Para o Modelo 2, o custo dos erros é assimétrico:
um falso positivo gasta uma diligência à toa; um falso negativo abandona
dinheiro recuperável. Com o corte padrão de 0,5, o recall é de **0,540**:
quase metade das dívidas recuperáveis fica abaixo do corte. O pipeline de
demonstração mantém 0,5; num uso real, o corte de decisão deve ser escolhido na validação
pelo custo de cada erro, como mostra a aula da Sprint 4. A fila de cobrança não
depende do corte — ela ordena pela probabilidade contínua.

---

## 5. Dados de treinamento

| Origem | Natureza | Uso |
|---|---|---|
| API REST da Prefeitura de Palmas (`sgreceitas/listar`) | **Real** — 17.507 registros de arrecadação de 2025 | Contexto agregado, calibração |
| Carteira de contribuintes (`src/sintetico.py`) | **Sintética** — 20.000 imóveis | Treino e avaliação |

**Calibração.** Três números publicados ancoram a carteira:

| Grandeza | Na carteira | Referência |
|---|---|---|
| Dívida ativa de IPTU | R$ 65,3 mi | R$ 363 mi (Sefin), na razão entre os 20.000 imóveis da amostra e os 111.252 tributáveis |
| Imóveis com dívida inscrita | 43,8% | **Hipótese**: 44%, a inadimplência no IPTU de Palmas medida em 2018 (TV Anhanguera). A Sefin não publica o número de devedores |
| Inadimplência no próximo exercício | 44,0% | A mesma medição de 2018. A meta oficial de 67% de adimplência em 2026 indica patamar acima de 33% |

Para fechar o total de R$ 363 mi, só a dívida é reescalada: o fator, cerca de
2,2 vezes o IPTU dos exercícios em aberto, representa multa, juros, correção e
débitos anteriores à janela de cinco anos. Valor venal e IPTU não são alterados:
o IPTU médio da carteira, R$ 1.019, é compatível com a arrecadação de 2026
(R$ 43 mi pagos à vista por 51.421 contribuintes até março). Os parâmetros
ficam em `config.py`; com o número real de devedores da Sefin, o gerador se
recalibra sozinho.

**Sub-representação conhecida.** Imóveis irregulares ou não cadastrados —
concentrados em ocupações informais — estão ausentes por construção, assim como
estariam num cadastro real. O modelo não enxerga essa população.

**Distribuição da carteira:**

| Faixa de renda do setor | Imóveis | Com dívida inscrita | Taxa de inadimplência | Dívida média por devedor |
|---|---|---|---|---|
| baixa | 9.204 | 53,6% | 54,5% | R$ 5.373,72 |
| média | 6.841 | 39,8% | 38,7% | R$ 8.730,26 |
| alta | 3.955 | 27,7% | 28,9% | R$ 13.671,14 |

Note a tensão que estrutura todo o problema ético: setores de renda baixa
concentram **mais casos** de inadimplência, mas setores de renda alta concentram
**mais dinheiro** por caso.

---

## 6. Análise de viés

Testes aplicados: Paridade Demográfica e Igualdade de Oportunidade. Limite de
disparidade adotado: 0,10 de diferença, convenção do AI Fairness 360 (Bellamy et al.,
2019); a regra dos quatro quintos da EEOC (1978), que olha a razão entre as
taxas e pede ao menos 0,8, aparece no RIA como segunda referência. Detalhamento
completo, com intervalos de confiança, no [RIA](RIA.md), seção 2.

### Modelo 1 — inadimplência: **reprovado**

| Grupo | n | Prevalência real | Taxa de seleção | Recall (TPR) |
|---|---|---|---|---|
| alta | 1.030 | 0,293 | 0,203 | 0,450 |
| média | 1.674 | 0,376 | 0,341 | 0,640 |
| baixa | 1.966 | 0,555 | 0,535 | 0,775 |

- Paridade Demográfica: **0,3322** (limite 0,10) — reprovado
- Igualdade de Oportunidade: **0,3251** (limite 0,10) — reprovado

### Modelo 2 — recuperabilidade: **reprovado, com viés no sentido oposto**

| Grupo | n | Prevalência real | Taxa de seleção | Recall (TPR) |
|---|---|---|---|---|
| alta | 256 | 0,484 | 0,500 | 0,629 |
| média | 691 | 0,450 | 0,386 | 0,540 |
| baixa | 1.064 | 0,402 | 0,380 | 0,514 |

- Paridade Demográfica: **0,1203** (limite 0,10) — reprovado; IC 95% de
  0,059 a 0,194
- Igualdade de Oportunidade: **0,1150** (limite 0,10) — reprovado; IC 95% de
  0,036 a 0,215
- Os intervalos contêm 0,10: com 256 casos de renda alta no teste, a amostra
  não distingue a disparidade real do limite. O critério não muda por isso — a
  aprovação é a estimativa pontual contra o limite fixado antes.
- Com corte calibrado por grupo (`src/fairness.py::simular_mitigacao`), a
  disparidade na taxa de seleção cai para **0,0008**.

**O achado central.** Os dois modelos são enviesados, em sentidos opostos e com
intensidades muito diferentes. O que prediz *quem deve* sinaliza 53,5% dos
setores de renda baixa contra 20,3% dos de renda alta — reflexo direto da
prevalência real (0,555 contra 0,293), que qualquer classificador calibrado
reproduz. O que prediz *de quem se recupera* favorece os setores de renda alta
(50,0% contra 38,0%) e reconhece menos as dívidas recuperáveis dos setores
pobres (recall de 0,514 contra 0,629). Esse viés é menor, mas passa do limite:
a recuperação também difere entre grupos (0,484 contra 0,402), e entre os
atributos mais importantes estão valor venal e distância ao centro, que
funcionam como substitutos da renda.

**Consequência prática, e é a recomendação mais importante deste documento:** o
Modelo 1 **não deve ser usado para direcionar cobrança**. Seu uso legítimo é
diagnóstico — dimensionar o problema, planejar campanhas de educação fiscal,
identificar setores que precisam de política pública. Quem ordena a fila é o
Modelo 2, **e só com o corte calibrado por grupo**: sem essa mitigação, ele
também reprova na auditoria.

---

## 7. Recomendações e cuidados

1. **Nunca automatizar a decisão.** O sistema produz ordenação, não veredito.
2. **Auditar a cada retreino**, com os mesmos dois testes, e publicar o
   resultado. Uma auditoria que não é publicada não cumpre sua função.
3. **Manter a exclusão do IPTU Social** verificada por teste automatizado, não
   por disciplina de quem opera.
4. **Registrar toda predição** que motive ação de cobrança (score, versão do
   modelo, data), para viabilizar contestação.
5. **Revisar o proxy de renda.** Faixa de renda por setor é grosseira; se o
   convênio com o IBGE permitir setor censitário real, refazer a auditoria.
6. **Reavaliar em 12 meses** ou após mudança relevante na legislação tributária
   municipal — o que ocorrer primeiro.
7. **Não migrar entre municípios** sem novo treino e nova auditoria.

---

## 8. Contato e contestação

| | |
|---|---|
| **Responsável acadêmico** | Prof. Dr. David Nadler Prata — Coordenação do Eixo II |
| **Instituição** | Bacharelado Interdisciplinar em Inteligência Artificial — UFT |
| **Equipe** | *(preencher: nomes e matrículas)* |
| **Canal de contestação** | *(em produção: ouvidoria da Sefin, com prazo de resposta definido)* |

Em uso real, o contribuinte classificado como de alto risco tem direito a
solicitar revisão humana da decisão, nos termos do Art. 20 da LGPD. O canal deve
ser divulgado no próprio documento de cobrança — não apenas neste Model Card.

---

## Referências

- MITCHELL, M. et al. *Model Cards for Model Reporting*. ACM FAccT, 2019.
- BAROCAS, S.; HARDT, M.; NARAYANAN, A. *Fairness and Machine Learning*, 2023.
- BELLAMY, R. K. E. et al. *AI Fairness 360: An Extensible Toolkit for
  Detecting and Mitigating Algorithmic Bias*. IBM Journal of Research and
  Development, v. 63, n. 4/5, 2019.
- EEOC. *Uniform Guidelines on Employee Selection Procedures*, 29 CFR 1607,
  1978 (regra dos quatro quintos).
- HARDT, M.; PRICE, E.; SREBRO, N. *Equality of Opportunity in Supervised
  Learning*. NeurIPS, 2016.
- BRASIL. Lei n. 13.709/2018 (LGPD).
