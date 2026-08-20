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
| **Universo de treino** | 18.607 imóveis (após exclusão do IPTU Social) | 15.361 imóveis com dívida inscrita |
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

### Modelo 1 — inadimplência (n = 4.652)

| Métrica | Valor |
|---|---|
| Acurácia | 0,652 |
| Precisão | 0,664 |
| Recall | 0,634 |
| F1-score | 0,649 |
| ROC-AUC | 0,702 |

Matriz de confusão `[[VN, FP], [FN, VP]]` = `[[1537, 756], [863, 1496]]`

### Modelo 2 — recuperabilidade (n = 3.841)

| Métrica | Valor |
|---|---|
| Acurácia | 0,620 |
| Precisão | 0,616 |
| Recall | 0,698 |
| F1-score | 0,654 |
| ROC-AUC | 0,666 |

Matriz de confusão `[[VN, FP], [FN, VP]]` = `[[998, 863], [598, 1382]]`

**Leitura honesta destes números.** ROC-AUC entre 0,67 e 0,70 é desempenho
moderado: o modelo é claramente melhor que o acaso, mas erra com frequência.
Isso é esperado e desejável num PoC cujo processo gerador embute ruído
deliberado. Métricas próximas de 1,0 aqui indicariam vazamento de dados, não
qualidade. Em produção, com histórico real de pagamentos, espera-se desempenho
superior — mas a decisão de tratar o resultado como **fila de trabalho**, e não
como veredito, permanece válida em qualquer nível de acurácia.

**Métrica que mais importa.** Para o Modelo 2, o custo dos erros é assimétrico:
um falso positivo gasta uma diligência à toa; um falso negativo abandona
dinheiro recuperável. Por isso o limiar foi mantido em 0,5 privilegiando
**recall** (0,698) sobre precisão (0,616).

---

## 5. Dados de treinamento

| Origem | Natureza | Uso |
|---|---|---|
| API REST da Prefeitura de Palmas (`sgreceitas/listar`) | **Real** — 17.507 registros de arrecadação de 2025 | Contexto agregado, calibração |
| Carteira de contribuintes (`src/sintetico.py`) | **Sintética** — 20.000 imóveis | Treino e avaliação |

**Calibração.** Os valores monetários são reescalados para que a dívida ativa da
amostra seja proporcional aos R$ 363 milhões de IPTU inscritos em dívida ativa
(Sefin), na razão entre os 20.000 imóveis da amostra e os 111.252 imóveis
tributáveis do município.

**Sub-representação conhecida.** Imóveis irregulares ou não cadastrados —
concentrados em ocupações informais — estão ausentes por construção, assim como
estariam num cadastro real. O modelo não enxerga essa população.

**Distribuição da carteira:**

| Faixa de renda do setor | Imóveis | Taxa de inadimplência | Dívida média |
|---|---|---|---|
| baixa | 9.204 | 59,6% | R$ 2.389,95 |
| média | 6.841 | 47,4% | R$ 3.536,09 |
| alta | 3.955 | 37,8% | R$ 4.821,70 |

Note a tensão que estrutura todo o problema ético: setores de renda baixa
concentram **mais casos** de inadimplência, mas setores de renda alta concentram
**mais dinheiro** por caso.

---

## 6. Análise de viés

Testes aplicados: Paridade Demográfica e Igualdade de Oportunidade. Limiar
adotado: 0,10 (Barocas, Hardt e Narayanan, 2023). Detalhamento completo no
[RIA](RIA.md), seção 2.

### Modelo 1 — inadimplência: **reprovado**

| Grupo | n | Prevalência real | Taxa de seleção | Recall (TPR) |
|---|---|---|---|---|
| alta | 1.028 | 0,367 | 0,203 | 0,310 |
| média | 1.647 | 0,477 | 0,427 | 0,559 |
| baixa | 1.977 | 0,605 | 0,678 | 0,786 |

- Paridade Demográfica: **0,4745** (limiar 0,10) — reprovado
- Igualdade de Oportunidade: **0,4757** (limiar 0,10) — reprovado

### Modelo 2 — recuperabilidade: **aprovado**

| Grupo | n | Prevalência real | Taxa de seleção | Recall (TPR) |
|---|---|---|---|---|
| alta | 704 | 0,548 | 0,619 | 0,723 |
| média | 1.362 | 0,499 | 0,583 | 0,706 |
| baixa | 1.775 | 0,515 | 0,572 | 0,682 |

- Paridade Demográfica: **0,0475** — aprovado
- Igualdade de Oportunidade: **0,0412** — aprovado

**O achado central.** O modelo que prediz *quem deve* é fortemente enviesado; o
modelo que prediz *de quem se recupera* é razoavelmente equilibrado. A diferença
não é acidente de modelagem: a inadimplência tem prevalência real muito diferente
entre grupos (0,367 contra 0,605), então qualquer classificador calibrado
reproduz essa diferença. A recuperabilidade, ao contrário, tem prevalência
parecida em todos os grupos (0,50 a 0,55) — recuperar dívida depende mais do
tempo de inscrição e do histórico de parcelamento do que da renda do setor.

**Consequência prática, e é a recomendação mais importante deste documento:** o
Modelo 1 **não deve ser usado para direcionar cobrança**. Seu uso legítimo é
diagnóstico — dimensionar o problema, planejar campanhas de educação fiscal,
identificar setores que precisam de política pública. Quem ordena a fila é o
Modelo 2.

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
- HARDT, M.; PRICE, E.; SREBRO, N. *Equality of Opportunity in Supervised
  Learning*. NeurIPS, 2016.
- BRASIL. Lei n. 13.709/2018 (LGPD).
