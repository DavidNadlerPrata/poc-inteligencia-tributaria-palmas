# Aula — Sprint 4, E3: notebook documentado e modelo serializado

Material de apoio para o entregável **E3** da Sprint 4 (Módulo 6 — Introdução à
Inteligência Artificial): *"Notebook Jupyter com a trilha completa (EDA →
pré-processamento → treinamento → avaliação) e o modelo salvo (.pkl/.joblib)
versionado em /models."*

> **Sobre a numeração.** No plano de ensino original esta etapa aparece como
> Sprint 3; o enunciado da tarefa a numera como Sprint 4 e chama a etapa de
> governança de Sprint 5. Este material segue o enunciado.

**Como usar este material.** Os blocos de código formam uma trilha única: copie
cada um para uma célula do notebook, na ordem em que aparecem, e ele executa do
início ao fim. Os blocos que começam com `# ERRADO` ou `# ARMADILHA` são
contraexemplos — leia, não copie. Todos os números citados aqui saíram da
execução destes mesmos blocos sobre a carteira versionada no repositório, e um
teste automatizado reexecuta a trilha a cada alteração.

**O que você precisa ter antes:** o repositório clonado, as dependências
instaladas (`pip install -r requirements.txt`) e a carteira em
`data/carteira_contribuintes.csv`. Crie o notebook em
`notebooks/sprint4_modelos.ipynb` — os caminhos relativos da trilha partem daí.

---

## Antes de começar: o E3 não é só o arquivo

O E3 vale 15% da rubrica, mas é ele que **carrega** o E1 (metodologia, 25%) e o
E2 (modelos e métricas, 30%). O notebook é onde a banca vai verificar se o
split temporal está correto e se as métricas foram interpretadas — ou seja,
70% da nota da sprint passa por este arquivo.

Então o critério não é "o notebook roda". É:

> Alguém que não participou do projeto consegue abrir o notebook, entender cada
> decisão, executá-lo do início ao fim e obter os mesmos números?

O enunciado pede **dois modelos**, e a trilha entrega os dois:

| Modelo | Pergunta | Universo | Alvo |
|---|---|---|---|
| 1 — classificação de inadimplência | O contribuinte ficará inadimplente no próximo exercício? | Todos os contribuintes | `inadimplente_proximo_exercicio` |
| 2 — scoring de recuperabilidade | Uma dívida já inscrita será recuperada em 12 meses? | Só quem tem dívida inscrita | `divida_recuperada_12m` |

As seções 3 a 7 constroem o Modelo 1 passo a passo. A seção 8 aplica a mesma
receita ao Modelo 2, reaproveitando as funções já escritas.

---

## A estrutura: nove seções

Monte o notebook nesta ordem. Ela não é arbitrária — cada seção depende da
anterior, e inverter duas delas é exatamente como se cria vazamento de dados.

| # | Seção | Entregável |
|---|---|---|
| 1 | Cabeçalho, proveniência e preparação | E3 |
| 2 | Carga, exclusão do grupo protegido e EDA orientada a decisão | E3 |
| 3 | **Split temporal** | **E1** |
| 4 | Pré-processamento dentro do pipeline | E1 |
| 5 | Baselines comparados na validação | E1 |
| 6 | Modelo com tunagem e escolha do vencedor | E2 |
| 7 | Limiar, avaliação final e métricas por subgrupo | E2 |
| 8 | O segundo modelo: scoring de recuperabilidade | E2 |
| 9 | Serialização e versionamento | E3 |

---

## Seção 1 — Cabeçalho, proveniência e preparação

A primeira célula é Markdown, e ela tem uma exigência explícita no enunciado da
sprint: *"Se a camada individual do dado for sintética, declarem isso já no
notebook."*

Isso não é burocracia. Sem essa declaração, todo número que vem depois pode ser
lido como afirmação sobre a realidade fiscal de Palmas — e não é.

```markdown
# Sprint 4 — Modelo de predição de inadimplência e scoring de recuperabilidade

**Equipe:** [nomes e matrículas]
**Data de execução:** [data]
**Repositório:** [URL]

## Proveniência dos dados

| Camada | Origem | Natureza |
|---|---|---|
| Arrecadação agregada | API do portal de transparência, coletada em [data] | **Real** |
| Carteira de contribuintes | Gerador calibrado (`src/sintetico.py`) | **Sintética** |

**Declaração obrigatória.** A camada individual de dívida ativa é sintética,
calibrada pelos agregados oficiais da Sefin. O registro individual do
contribuinte é dado pessoal protegido pela LGPD e não é publicado por nenhuma
API municipal.

As métricas deste notebook demonstram que **o pipeline funciona** — não que o
modelo funcionaria no mundo real. Qualquer estimativa de desempenho real exige
recalibração sobre dados reais, mediante convênio.
```

A primeira célula de código reúne as importações, fixa a semente, define os
caminhos e registra as versões:

```python
import json
import platform
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

SEMENTE = 42
np.random.seed(SEMENTE)

# O notebook mora em notebooks/; dados e modelos ficam um nível acima.
DADOS = Path("../data")
MODELOS = Path("../models")
MODELOS.mkdir(exist_ok=True)

print(f"python  {platform.python_version()}")
print(f"pandas  {pd.__version__}")
print(f"sklearn {sklearn.__version__}")
print(f"joblib  {joblib.__version__}")
```

Sem a semente e as versões, "não reproduz na minha máquina" vira discussão sem
dados. E só caminhos relativos: um `C:\Users\...` no notebook quebra na máquina
de qualquer outra pessoa, inclusive na da banca.

---

## Seção 2 — Carga, exclusão do grupo protegido e EDA

### Carregue e exclua antes de qualquer outra coisa

```python
dados = pd.read_csv(DADOS / "carteira_contribuintes.csv", sep=";")
print(f"{len(dados)} registros, {dados.shape[1]} colunas")

# Beneficiários do IPTU Social saem ANTES de qualquer split, EDA ou treino.
universo = dados[dados["iptu_social"] == 0].copy()
print(f"excluídos pelo IPTU Social: {len(dados) - len(universo)} | universo: {len(universo)}")

assert universo["iptu_social"].sum() == 0, "grupo protegido ainda presente!"
```

A ordem importa. Idosos, aposentados, pensionistas e pessoas com deficiência de
baixa renda são isentos e não podem ser alvo de ação preditiva de cobrança. Se
a exclusão vier depois do split, eles já estarão dentro do conjunto de treino —
e nenhuma mensagem de erro vai avisar. Daqui em diante, **toda a trilha parte de
`universo`**, nunca de `dados`.

Nesta carteira saem 1.320 dos 20.000 registros, e o universo de trabalho
fica com 18.680.

### EDA orientada a decisão

Você já fez a análise exploratória na Sprint de coleta e ETL. **Não repita
aqui.** Esta seção é curta e tem um único propósito: mostrar os fatos que
justificam as decisões de modelagem que vêm a seguir. Para cada gráfico ou
tabela, pergunte: *que decisão isto sustenta?* Se não sustenta nenhuma, tire do
notebook.

```python
# 1) Balanceamento dos alvos -- decide se precisa de class_weight ou reamostragem
print(universo["inadimplente_proximo_exercicio"].value_counts(normalize=True).round(3))

# 2) Universo do segundo modelo -- só faz sentido para quem tem dívida inscrita
tem_divida = universo["valor_divida_consolidada"] > 0
print(f"com dívida inscrita: {tem_divida.sum()} de {len(universo)}")
print(universo.loc[tem_divida, "divida_recuperada_12m"].value_counts(normalize=True).round(3))
```

Feche a seção com uma célula Markdown listando as decisões tomadas:

> **Decisões que a EDA sustenta**
>
> 1. Os dois alvos estão equilibrados (43,3% de inadimplentes) → não
>    usaremos reamostragem nem `class_weight`.
> 2. O Modelo 2 usa só os 8.041 registros com dívida inscrita.
> 3. Os 1.320 beneficiários do IPTU Social saíram antes de qualquer treino.

---

## Seção 3 — Split temporal (o coração do E1)

Esta é a seção mais importante do notebook e a que a banca vai atacar primeiro.
O enunciado avisa: *"nada do futuro pode informar o passado no treino — a banca
vai perguntar."*

### 3.1 Por que `train_test_split` aleatório reprova aqui

```python
# ERRADO para este problema -- não copie
from sklearn.model_selection import train_test_split
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y)
```

O split aleatório mistura períodos: o modelo treina com dados de 2026 e é
testado em dados de 2024. Na operação real isso é impossível — você só tem o
passado para prever o futuro. Com dados reais, um split aleatório
**superestima** o desempenho, porque o modelo viu padrões de um período que, na
vida real, ainda não existiria.

> **Nota sobre o PoC de referência.** O `src/modelo.py` do PoC usa
> `train_test_split` estratificado, e **não atende** a este requisito. Ele foi
> construído para demonstrar o encadeamento das etapas, não a metodologia
> temporal da Sprint 4. Use-o como referência de estrutura (pipeline,
> serialização, auditoria) e implemente o split temporal por conta — é
> justamente o que está sendo avaliado.

### 3.2 A armadilha: não derive a data do seu melhor preditor

A carteira sintética **não tem coluna de data de competência**. É tentador
derivar uma a partir de `tempo_inadimplencia_dias`:

```python
# ARMADILHA -- parece razoável e produz um split inútil. Não copie.
dados["data_inscricao"] = HOJE - pd.to_timedelta(dados["tempo_inadimplencia_dias"], unit="D")
```

Medimos o resultado disso nos registros com dívida, cortando nos 20% mais
recentes:

| Conjunto | Tempo médio de inadimplência | Taxa de recuperação |
|---|---|---|
| treino (80% mais antigo) | 1.419 dias | 37,6% |
| teste (20% mais recente) | 292 dias | 64,4% |

O corte temporal passou a separar **exatamente pelo preditor mais forte** do
Modelo 2. O teste ficou só com dívidas recentes, cuja taxa de recuperação é
muito maior. As distribuições são incomparáveis, e qualquer métrica calculada
ali é enganosa.

**A lição geral:** o eixo temporal precisa ser **independente** dos atributos
preditivos. Se o seu "tempo" é função de uma feature, não é um eixo temporal —
é a própria feature disfarçada.

### 3.3 O eixo temporal correto: competência do registro

No dado real, a dívida ativa é uma **foto mensal**: cada registro diz como o
contribuinte estava em determinado mês de competência. É esse campo que define o
eixo temporal.

A carteira sintética não tem esse campo, então a trilha acrescenta um mês de
competência independente de qualquer atributo:

```python
rng = np.random.default_rng(SEMENTE)

# Competência: mês de referência do registro. Independente de qualquer atributo.
meses = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
universo["competencia"] = rng.choice(meses, size=len(universo))

# Ordem cronológica: a validação temporal da seção 3.6 depende dela.
universo = universo.sort_values("competencia").reset_index(drop=True)
```

Documente essa escolha no notebook. Inventar um eixo temporal é aceitável em
PoC — **esconder que você inventou, não é**.

> **O que este eixo ensina e o que ele não prova.** Como a competência foi
> sorteada, não existe deriva temporal nesta base: o passado e o futuro têm a
> mesma distribuição, e o split temporal equivale, por construção, a um split
> aleatório. Medimos: em 20 splits aleatórios do mesmo tamanho, o ROC-AUC de
> teste variou de 0,785 a 0,814; o do split temporal,
> 0,803, cai dentro dessa faixa. Ou seja, aqui você exercita a
> **mecânica** correta — cortar por data, validar no futuro, provar a ausência
> de vazamento —, mas não vai observar o efeito que ela protege. Com dados
> reais, em que a economia e a política de cobrança mudam de um ano para outro,
> a diferença aparece. Diga isso no notebook: a banca valoriza quem sabe o que o
> próprio experimento não demonstra.

> **Repare na largura dessa faixa.** Ela mostra quanto uma métrica de teste
> oscila só por sorteio, sem que nada tenha mudado no modelo. Guarde esse número
> para a seção 6: diferenças de poucos milésimos entre dois modelos estão
> dentro do ruído.

### 3.4 Fazendo o corte

```python
CORTE_TESTE = pd.Timestamp("2026-04-01")      # os últimos 7 meses ficam para teste

treino = universo[universo["competencia"] < CORTE_TESTE]
teste = universo[universo["competencia"] >= CORTE_TESTE]

print(f"treino: {len(treino):5d} ({len(treino) / len(universo):.0%})"
      f" | até {treino['competencia'].max().date()}")
print(f"teste:  {len(teste):5d} ({len(teste) / len(universo):.0%})"
      f" | de {teste['competencia'].min().date()}")
```

Com esta base: 14.936 registros de treino (80%) e 3.744 de
teste (20%).

### 3.5 Provando que não há vazamento

Não afirme que não há vazamento: **demonstre**. Três verificações, em código, no
notebook:

```python
# 1) Não há sobreposição temporal
assert treino["competencia"].max() < teste["competencia"].min(), "sobreposição temporal!"

# 2) Nenhum registro está nos dois lados
#    (nesta carteira cada contribuinte aparece uma única vez)
repetidos = set(treino["id_contribuinte"]) & set(teste["id_contribuinte"])
assert not repetidos, f"{len(repetidos)} contribuintes em treino e teste"

# 3) As distribuições são comparáveis (se não forem, o corte está ruim)
colunas = ["valor_venal", "exercicios_inadimplentes_5a", "inadimplente_proximo_exercicio"]
comparacao_split = pd.DataFrame({"treino": treino[colunas].mean(),
                                 "teste": teste[colunas].mean()}).round(3)
print(comparacao_split)
```

Com o eixo de competência, a comparação fica assim — e é isso que você quer ver:

| Média | Treino | Teste |
|---|---|---|
| Valor venal (R$) | 177.635 | 173.908 |
| Exercícios inadimplentes (5 anos) | 1,62 | 1,63 |
| Taxa de inadimplência | 43,1% | 44,1% |

Esses `assert` são o seu seguro na banca. Quando perguntarem sobre vazamento,
você rola até a célula e mostra a verificação rodando.

> **Atenção com dados reais em formato de painel.** A verificação 2 vale para
> esta carteira, em que cada contribuinte tem uma linha só. Numa base real de
> fotos mensais, o mesmo contribuinte aparece em várias competências — e é
> legítimo que esteja no treino (meses antigos) e no teste (meses recentes).
> Nesse formato, troque a verificação: confira que nenhuma **linha** se repete
> e, principalmente, que nenhum atributo foi calculado com informação posterior
> à competência da linha (um "total pago no ano", por exemplo, numa linha de
> março).

### 3.6 E a validação?

O enunciado pede treino/teste/**validação**. Com eixo temporal, a validação sai
de dentro do treino, respeitando a ordem:

```python
# 4 dobras: cada uma ajusta no passado e valida no futuro imediato
validacao_temporal = TimeSeriesSplit(n_splits=4)
```

É com essas dobras que você vai comparar modelos, tunar hiperparâmetros e
escolher o limiar de decisão. **O conjunto de teste fica guardado até a
seção 7** e é usado uma única vez.

Duas regras:

- **Nunca** use `KFold` ou `cross_val_score` com embaralhamento: eles recriam o
  vazamento que você acabou de eliminar.
- O `TimeSeriesSplit` divide por **posição na tabela**, não por data. Ele só é
  temporal porque ordenamos `universo` por competência na seção 3.3. Se você
  reordenar ou embaralhar o DataFrame depois, a proteção se perde em silêncio.

---

## Seção 4 — Pré-processamento dentro do pipeline

### O erro que mais reprova

```python
# ERRADO -- vazamento silencioso. Não copie.
from sklearn.preprocessing import StandardScaler
escalador = StandardScaler().fit(X)        # <-- viu treino E teste
X_tr = escalador.transform(X_tr)
X_te = escalador.transform(X_te)
```

O `fit` calculou média e desvio usando **o conjunto de teste inteiro**.
Informação do teste vazou para o treino, e a métrica final fica otimista. Não dá
erro, não dá aviso — e é uma das primeiras coisas que a banca procura.

### Atributos, alvo e o que fica de fora

```python
CATEGORICOS = ["tipo_imovel", "setor_urbano"]
NUMERICOS = ["area_construida_m2", "valor_venal", "valor_iptu_anual",
             "distancia_centro_km", "exercicios_inadimplentes_5a",
             "tempo_inadimplencia_dias", "valor_divida_consolidada",
             "qtd_parcelamentos_anteriores", "parcelamento_rompido",
             "qtd_notificacoes"]
ATRIBUTOS = CATEGORICOS + NUMERICOS

ALVO = "inadimplente_proximo_exercicio"          # Modelo 1

X_treino, y_treino = treino[ATRIBUTOS], treino[ALVO]
X_teste, y_teste = teste[ATRIBUTOS], teste[ALVO]

# Três coisas que NÃO podem estar entre os atributos:
PROIBIDOS = {"inadimplente_proximo_exercicio", "divida_recuperada_12m",   # os alvos
             "faixa_renda_setor",                                        # grupo protegido
             "iptu_social", "competencia", "id_contribuinte"}
assert not (PROIBIDOS & set(ATRIBUTOS)), "coluna proibida entre os atributos!"
```

Por que cada uma fica de fora:

- **Os alvos.** Alvo entre os preditores é o vazamento mais grosseiro: a métrica
  vai para perto de 1,0 e o modelo não serve para nada.
- **`faixa_renda_setor`.** É o grupo protegido. Usá-la como preditor é
  discriminação direta por renda; ela fica guardada para a auditoria de fairness
  da Sprint 5.
- **`iptu_social`.** Dado sensível (LGPD, Art. 5º, II), usado só para excluir.
- **`competencia` e `id_contribuinte`.** Servem para organizar o experimento,
  não para prever.

### A forma correta: tudo dentro de um `Pipeline`

```python
def montar_preparo():
    """Pré-processamento. Uma instância nova a cada chamada, para cada modelo."""
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICOS),
        ("num", Pipeline([
            ("imputacao", SimpleImputer(strategy="median")),
            ("escala", StandardScaler()),
        ]), NUMERICOS),
    ])


def montar_modelo(estimador):
    """Pré-processamento + classificador num objeto só."""
    return Pipeline([("preparo", montar_preparo()), ("classificador", estimador)])
```

Por que isso resolve: o `Pipeline` só faz `fit` no que você passar para ele.
Durante a validação, ele refaz o `fit` em cada dobra automaticamente, usando só
a parte de ajuste. Você não consegue vazar por descuido.

**`handle_unknown="ignore"` não é opcional** com split temporal: pode aparecer
no teste uma categoria que não existia no treino (um setor novo). Sem isso, o
notebook quebra na hora da avaliação.

---

## Seção 5 — Baselines comparados na validação (E1)

O enunciado pede explicitamente **Regressão Logística e Árvore de Decisão** como
referência. Baseline não é formalidade: é o número que dá sentido ao resultado
final. Um Random Forest com ROC-AUC 0,70 é bom ou ruim? Só o baseline responde.

A comparação acontece **na validação**, não no teste:

```python
def comparar_na_validacao(candidatos, X, y):
    """ROC-AUC e F1 médios nas dobras de validação temporal."""
    linhas = []
    for nome, estimador in candidatos.items():
        notas = cross_validate(montar_modelo(estimador), X, y,
                               cv=validacao_temporal, scoring=["roc_auc", "f1"])
        # O scikit-learn chama de "test_" a nota da dobra de validação.
        linhas.append({"modelo": nome,
                       "roc_auc": notas["test_roc_auc"].mean(),
                       "f1": notas["test_f1"].mean()})
    return pd.DataFrame(linhas).round(4)


baselines = {
    "trivial (maioria)": DummyClassifier(strategy="most_frequent"),
    "regressão logística": LogisticRegression(max_iter=1000, random_state=SEMENTE),
    "árvore de decisão": DecisionTreeClassifier(max_depth=5, random_state=SEMENTE),
}

placar = comparar_na_validacao(baselines, X_treino, y_treino)
print(placar)
```

Inclua o **classificador trivial**. Se o seu modelo sofisticado não superar
"chutar sempre a classe majoritária", isso precisa aparecer no notebook — e é
melhor você descobrir antes da banca.

### O que o classificador trivial ensina

O placar desta base:

| Modelo | ROC-AUC na validação | F1 na validação |
|---|---|---|
| trivial (maioria) | 0,5000 | 0,0000 |
| regressão logística | 0,7998 | 0,7132 |
| árvore de decisão | 0,7885 | 0,7113 |

O trivial prevê sempre a classe majoritária, e nesta base ela é **adimplente**:
só 42,8% dos registros de validação são inadimplentes. Por isso ele
**acerta 57,2% dos casos sem identificar um único inadimplente** —
recall zero, F1 zero e ROC-AUC 0,500, porque dá a mesma previsão a todos.

**A armadilha é a acurácia.** "O modelo acerta 76,7%" impressiona até
alguém lembrar que não fazer nada acerta 57,2%. A acurácia sozinha não diz
quanto o modelo aprendeu, e ela muda com a prevalência: numa carteira com 90%
de adimplentes, o trivial acertaria 90%.

**O F1 também depende de uma escolha.** Ele é calculado depois de cortar as
probabilidades num limiar, e o padrão da biblioteca é 0,5. O ROC-AUC não
depende de limiar: mede se o modelo põe os inadimplentes à frente dos
adimplentes na ordenação. Para ver o efeito do limiar, precisamos das
probabilidades que o modelo atribui aos registros de validação:

```python
def previsoes_de_validacao(modelo, X, y):
    """Probabilidades previstas para as dobras de validação.

    Cada registro é previsto por um modelo que não o viu no ajuste.
    """
    probabilidades, reais = [], []
    for idx_ajuste, idx_validacao in validacao_temporal.split(X):
        ajustado = clone(modelo).fit(X.iloc[idx_ajuste], y.iloc[idx_ajuste])
        probabilidades.append(ajustado.predict_proba(X.iloc[idx_validacao])[:, 1])
        reais.append(y.iloc[idx_validacao].to_numpy())
    return np.concatenate(probabilidades), np.concatenate(reais)


logistica = montar_modelo(LogisticRegression(max_iter=1000, random_state=SEMENTE))
prob_val, y_val = previsoes_de_validacao(logistica, X_treino, y_treino)

for limiar in (0.35, 0.40, 0.45, 0.50, 0.55):
    previsto = prob_val >= limiar
    print(f"limiar {limiar:.2f} | F1 {f1_score(y_val, previsto):.4f}"
          f" | precisão {precision_score(y_val, previsto):.3f}"
          f" | recall {recall_score(y_val, previsto):.3f}")
```

O F1 da regressão logística em vários limiares, na validação:

| Limiar | F1 | Precisão | Recall |
|---|---|---|---|
| 0,35 | 0,7204 | 0,724 | 0,717 |
| 0,40 | 0,7204 | 0,737 | 0,704 |
| 0,45 | 0,7174 | 0,749 | 0,688 |
| 0,50 | 0,7132 | 0,755 | 0,676 |
| 0,55 | 0,7018 | 0,766 | 0,647 |

Nesta base o F1 muda pouco: 0,7132 no limiar 0,5 e 0,7219 no melhor
limiar (0,38). O que muda bastante é a troca entre precisão e recall —
e é por ela que o limiar se escolhe (seção 7). Em outra base, com outra
prevalência, o corte em 0,5 pode esconder um modelo bom; por isso a comparação
entre modelos não deve depender dele.

**Três conclusões para o notebook:**

1. **Compare modelos por ROC-AUC**, que não depende de limiar. Use F1 para
   avaliar uma configuração de decisão específica.
2. **O limiar é uma decisão de projeto**, não uma constante da biblioteca
   (seção 7).
3. **Reporte a acurácia do trivial ao lado da sua.** É ela que mostra quanto o
   modelo acrescenta: nesta base, a regressão logística acerta 76,7%
   dos casos de validação no limiar 0,5, contra 57,2% do trivial.

---

## Seção 6 — Modelo com tunagem e escolha do vencedor (E2)

### Tunagem com validação temporal

O enunciado pede um modelo mais expressivo (cita Random Forest e XGBoost como
exemplos) com tunagem de hiperparâmetros:

```python
grade = {
    "classificador__n_estimators": [200],
    "classificador__max_depth": [6, 10],
    "classificador__min_samples_leaf": [5, 20],
}

busca = GridSearchCV(
    montar_modelo(RandomForestClassifier(random_state=SEMENTE, n_jobs=-1)),
    grade,
    cv=validacao_temporal,          # <-- temporal, não KFold
    scoring="roc_auc",
    n_jobs=-1,
)
busca.fit(X_treino, y_treino)       # <-- só o treino; o teste nem aparece

print("melhores parâmetros:", busca.best_params_)
print(f"ROC-AUC na validação: {busca.best_score_:.4f}")
```

Note o prefixo `classificador__`: dentro de um `Pipeline`, os parâmetros são
endereçados pelo nome do passo com dois sublinhados.

A grade acima é pequena de propósito: quatro combinações rodam em segundos.
Amplie quando a trilha inteira estiver funcionando — mas com um cuidado
prático: florestas sem limite de profundidade ficam enormes. Nesta base, 400
árvores com `max_depth=None` e `min_samples_leaf=1` geram um arquivo de mais de
190 MB, acima do limite de 100 MB do GitHub (seção 9).

### O placar decide — não a sofisticação

Junte o resultado da tunagem ao placar dos baselines:

```python
placar_final = pd.concat([
    placar[["modelo", "roc_auc"]],
    pd.DataFrame([{"modelo": "random forest (tunado)",
                   "roc_auc": round(busca.best_score_, 4)}]),
], ignore_index=True).sort_values("roc_auc", ascending=False)
print(placar_final)
```

| Modelo | ROC-AUC na validação |
|---|---|
| regressão logística | 0,7998 |
| random forest (tunado) | 0,7980 |
| árvore de decisão | 0,7885 |
| trivial (maioria) | 0,5000 |

**A regressão logística vence o Random Forest tunado.** A diferença é pequena
(0,002 de ROC-AUC) — menor que a oscilação por sorteio medida na seção 3.3,
portanto um empate técnico. Por isso a regra de decisão precisa ser fixada
antes de olhar o resultado, e a nossa é: *vence o maior ROC-AUC na validação; em empate
técnico, vence o modelo mais simples*. Pelas duas cláusulas, o escolhido é a
regressão logística.

```python
# Substitua pelo vencedor do SEU placar.
vencedor = montar_modelo(LogisticRegression(max_iter=1000, random_state=SEMENTE))
```

Isso não é um fracasso do trabalho — é um resultado. Escreva-o assim:

> **Justificativa da escolha.** Comparamos quatro candidatos na validação
> temporal. O Random Forest, tunado em quatro combinações de profundidade e
> tamanho mínimo de folha, atingiu ROC-AUC de 0,798; a regressão logística,
> 0,800. Escolhemos a regressão logística: tem o melhor desempenho de
> validação, é o modelo mais simples e seus coeficientes são diretamente
> interpretáveis, o que sustenta o direito à explicação do Art. 20 da LGPD. O
> resultado é coerente com a natureza dos dados: a carteira sintética foi
> gerada por um processo aproximadamente linear no logito, que é exatamente a
> forma funcional da regressão logística — não há interações para um modelo de
> árvores explorar. Com dados reais essa vantagem pode desaparecer, e a
> comparação deve ser refeita.

O enunciado cobra *"justificativa das escolhas algorítmicas"*. Uma justificativa
é isto: candidatos, critério, números e a razão do resultado. "Usamos Random
Forest porque é robusto" não é justificativa — e, nesta base, nem seria a
escolha certa.

---

## Seção 7 — Limiar, avaliação final e métricas por subgrupo

### Escolha o limiar na validação, pelo custo do erro

O limiar de 0,5 é só o padrão da biblioteca. Faça a sua escolha — e faça **na
validação**, porque escolher o limiar olhando o teste é ajustar o modelo ao
gabarito:

```python
prob_val, y_val = previsoes_de_validacao(vencedor, X_treino, y_treino)

limiares = np.arange(0.30, 0.71, 0.01)
f1_por_limiar = [f1_score(y_val, prob_val >= limiar) for limiar in limiares]
LIMIAR = round(float(limiares[int(np.argmax(f1_por_limiar))]), 2)

print(f"limiar que maximiza F1 na validação: {LIMIAR:.2f}")
for limiar in (0.50, LIMIAR):
    previsto = prob_val >= limiar
    print(f"  limiar {limiar:.2f}: recall {recall_score(y_val, previsto):.3f}"
          f" | precisão {precision_score(y_val, previsto):.3f}"
          f" | acertos {int((previsto & (y_val == 1)).sum())}"
          f" | alarmes falsos {int((previsto & (y_val == 0)).sum())}")
```

Mas atenção: **maximizar F1 não é automaticamente o certo**. O F1 trata falso
positivo e falso negativo como igualmente ruins, e no seu problema eles podem
não ser. Diga o que cada erro custa e mostre a troca em casos:

> **Nossa escolha de limiar.** Um falso negativo é um contribuinte que ficará
> inadimplente sem que a Sefin o antecipe; um falso positivo é um contribuinte
> em dia sinalizado indevidamente. Como este modelo tem uso diagnóstico —
> dimensionar a inadimplência esperada e orientar ações de educação fiscal, não
> cobrança —, o alarme falso custa pouco, e privilegiamos o recall. Com o limiar
> em 0,38, escolhido na validação, o recall sobe de 0,676 para
> 0,710: 176 inadimplentes a mais identificados
> (3.456 → 3.632), ao preço de 196 alarmes falsos
> adicionais (1.122 → 1.318). Se o modelo fosse usado para
> direcionar cobrança, esse custo seria inaceitável e a escolha seria outra.

> **Reporte a troca em casos, dos dois lados.** "O recall subiu 0,03" não
> significa nada para a Sefin; "176 inadimplentes a mais, com 196 alarmes
> falsos a mais" significa. E nunca cite só o ganho: o custo é metade da
> decisão.

### A avaliação final: o teste, uma única vez

Agora — e só agora — o conjunto de teste entra:

```python
def avaliar(y_real, probabilidades, limiar):
    """Métricas exigidas pelo enunciado, para um limiar de decisão."""
    previsto = (probabilidades >= limiar).astype(int)
    return {
        "acuracia": accuracy_score(y_real, previsto),
        "precisao": precision_score(y_real, previsto, zero_division=0),
        "recall": recall_score(y_real, previsto, zero_division=0),
        "f1": f1_score(y_real, previsto, zero_division=0),
        "roc_auc": roc_auc_score(y_real, probabilidades),
        "matriz_confusao": confusion_matrix(y_real, previsto).tolist(),
    }


modelo_inadimplencia = vencedor.fit(X_treino, y_treino)     # ajuste final: todo o treino
prob_teste = modelo_inadimplencia.predict_proba(X_teste)[:, 1]

metricas_inadimplencia = avaliar(y_teste, prob_teste, LIMIAR)
for nome, valor in metricas_inadimplencia.items():
    print(f"{nome:16s} {valor if isinstance(valor, list) else round(valor, 4)}")
```

Resultado no teste:

| Métrica | Valor |
|---|---|
| Acurácia | 0,771 |
| Precisão | 0,754 |
| Recall | 0,713 |
| F1 | 0,733 |
| ROC-AUC | 0,803 |

Matriz de confusão `[[VN, FP], [FN, VP]]` = `[[1708, 384], [474, 1178]]`

Se o resultado do teste decepcionar, **não volte para ajustar nada**. No momento
em que você altera o modelo por causa do teste, ele deixa de ser teste. Reporte
o número que saiu.

### Interprete, não só reporte

A rubrica diz *"métricas completas e interpretadas"*. Uma tabela de números sem
leitura não cumpre o critério. Para cada métrica, diga o que ela significa **no
problema**:

> A matriz de confusão mostra 474 falsos negativos: contribuintes que ficarão
> inadimplentes e que o modelo não antecipa. Os 384 falsos positivos são
> contribuintes em dia sinalizados indevidamente — aceitável num uso
> diagnóstico, inaceitável se a saída acionasse cobrança. O ROC-AUC de 0,803
> no teste ficou próximo do obtido na validação (0,800), o que indica que a
> estimativa de validação era confiável.

E seja honesto sobre o que o número significa:

> ROC-AUC de 0,803: o modelo é claramente melhor que o acaso e ainda erra com
> frequência — a matriz de confusão acima mostra quanto. Parte do erro é
> esperada, já que o processo gerador embute ruído deliberado. Valores
> próximos de 1,0 aqui indicariam vazamento, não qualidade.

### Métricas por subgrupo — guarde isto para a Sprint 5

O enunciado é explícito: *"Guardem as métricas POR SUBGRUPO (faixa de renda,
região): a Sprint 5 fará a análise de fairness sobre elas."*

```python
def metricas_por_grupo(avaliacao, coluna):
    """Prevalência, taxa de seleção, recall e precisão por grupo."""
    linhas = []
    for grupo, bloco in avaliacao.groupby(coluna):
        real, previsto = bloco["y_real"].to_numpy(), bloco["y_pred"].to_numpy()
        positivos = real == 1
        linhas.append({
            "grupo": grupo, "n": len(bloco),
            "prevalencia": real.mean(),
            "taxa_selecao": previsto.mean(),
            "recall": previsto[positivos].mean() if positivos.any() else np.nan,
            "precisao": real[previsto == 1].mean() if (previsto == 1).any() else np.nan,
        })
    return pd.DataFrame(linhas).round(4)


avaliacao_inadimplencia = pd.DataFrame({
    "id_contribuinte": teste["id_contribuinte"].to_numpy(),
    "faixa_renda_setor": teste["faixa_renda_setor"].to_numpy(),     # grupo protegido
    "setor_urbano": teste["setor_urbano"].to_numpy(),
    "y_real": y_teste.to_numpy(),
    "y_prob": prob_teste,
    "y_pred": (prob_teste >= LIMIAR).astype(int),
})

por_renda = metricas_por_grupo(avaliacao_inadimplencia, "faixa_renda_setor")
print(por_renda)

# A Sprint 5 vai consumir estes arquivos.
avaliacao_inadimplencia.to_csv(DADOS / "avaliacao_teste_inadimplencia.csv", sep=";", index=False)
por_renda.to_csv(DADOS / "metricas_por_subgrupo_inadimplencia.csv", sep=";", index=False)
```

| Faixa de renda do setor | n | Prevalência real | Taxa de seleção | Recall | Precisão |
|---|---|---|---|---|---|
| alta | 782 | 30,9% | 26,1% | 0,550 | 0,652 |
| media | 1.362 | 39,9% | 38,1% | 0,689 | 0,723 |
| baixa | 1.600 | 54,1% | 52,4% | 0,774 | 0,799 |

Olhe a coluna `taxa_selecao`: o modelo sinaliza 52% dos contribuintes
de setores de renda baixa e 26% dos de renda alta — mesmo sem a faixa de
renda entre os atributos. Nesta sprint você **mede e guarda**; a análise e a
mitigação são assunto da Sprint 5. Mas registre desde já: é por causa desse
número que o Modelo 1 fica restrito a uso diagnóstico.

Salvar o conjunto de teste com as predições é o que permite auditar fairness
depois **sem retreinar nada**. Equipe que não salva isso retrabalha.

---

## Seção 8 — O segundo modelo: scoring de recuperabilidade

O Modelo 2 responde a outra pergunta, sobre outro universo: entre os que **já
têm dívida inscrita**, qual a probabilidade de recuperação em 12 meses? A
receita é a mesma, e as funções já estão prontas:

```python
ALVO_REC = "divida_recuperada_12m"

# Mesmo corte temporal, universo restrito a quem tem dívida.
treino_rec = treino[treino["valor_divida_consolidada"] > 0]
teste_rec = teste[teste["valor_divida_consolidada"] > 0]

Xr_treino, yr_treino = treino_rec[ATRIBUTOS], treino_rec[ALVO_REC]
Xr_teste, yr_teste = teste_rec[ATRIBUTOS], teste_rec[ALVO_REC]
print(f"treino: {len(treino_rec)} | teste: {len(teste_rec)}")

# Baselines e tunagem, tudo na validação.
placar_rec = comparar_na_validacao(baselines, Xr_treino, yr_treino)

busca_rec = GridSearchCV(
    montar_modelo(RandomForestClassifier(random_state=SEMENTE, n_jobs=-1)),
    grade, cv=validacao_temporal, scoring="roc_auc", n_jobs=-1,
).fit(Xr_treino, yr_treino)

placar_rec_final = pd.concat([
    placar_rec[["modelo", "roc_auc"]],
    pd.DataFrame([{"modelo": "random forest (tunado)",
                   "roc_auc": round(busca_rec.best_score_, 4)}]),
], ignore_index=True).sort_values("roc_auc", ascending=False)
print(placar_rec_final)
```

| Modelo | ROC-AUC na validação |
|---|---|
| regressão logística | 0,7226 |
| random forest (tunado) | 0,7151 |
| árvore de decisão | 0,6872 |
| trivial (maioria) | 0,5000 |

De novo a regressão logística vence, pelo mesmo motivo. Ajuste final e
avaliação no teste, uma única vez:

```python
# Substitua pelo vencedor do SEU placar.
modelo_recuperabilidade = montar_modelo(
    LogisticRegression(max_iter=1000, random_state=SEMENTE)).fit(Xr_treino, yr_treino)

prob_rec = modelo_recuperabilidade.predict_proba(Xr_teste)[:, 1]
metricas_recuperabilidade = avaliar(yr_teste, prob_rec, 0.5)
print(f"ROC-AUC no teste: {metricas_recuperabilidade['roc_auc']:.4f}")
```

O ROC-AUC no teste é 0,691.

### Um score não tem limiar: tem faixas e ordenação

O Modelo 1 termina numa decisão binária, e por isso o limiar importava. O
Modelo 2 é um **scoring**: o que o MVP (E4) usa é a probabilidade em si, para
ordenar a fila. O enunciado pede as faixas alta/média/baixa:

```python
def faixa_recuperabilidade(probabilidade):
    """Traduz o score contínuo nas faixas exigidas pelo enunciado."""
    if probabilidade >= 0.66:
        return "alta"
    if probabilidade >= 0.33:
        return "media"
    return "baixa"


fila = teste_rec[["id_contribuinte", "setor_urbano", "faixa_renda_setor",
                  "valor_divida_consolidada"]].copy()
fila["y_real"] = yr_teste.to_numpy()
fila["prob_recuperacao"] = prob_rec
fila["faixa"] = fila["prob_recuperacao"].map(faixa_recuperabilidade)

# O que o MVP vai ordenar: retorno esperado = valor da dívida x probabilidade
fila["retorno_esperado"] = (fila["valor_divida_consolidada"] * fila["prob_recuperacao"]).round(2)
fila = fila.sort_values("retorno_esperado", ascending=False).reset_index(drop=True)
```

### Confira se as faixas dizem a verdade

Como o retorno esperado multiplica o valor pela probabilidade, não basta o
modelo **ordenar** bem: a probabilidade precisa ser um número confiável. A
verificação é simples — em cada faixa, a taxa de recuperação observada deve
acompanhar a probabilidade média prevista:

```python
calibracao = (fila.groupby("faixa")
              .agg(casos=("y_real", "size"),
                   prob_media_prevista=("prob_recuperacao", "mean"),
                   taxa_observada=("y_real", "mean"))
              .reindex(["alta", "media", "baixa"]).round(3))
print(calibracao)

# Guarde para o MVP (E4) e para a auditoria da Sprint 5.
fila.to_csv(DADOS / "avaliacao_teste_recuperabilidade.csv", sep=";", index=False)
```

| Faixa | Casos | Probabilidade média prevista | Taxa de recuperação observada |
|---|---|---|---|
| alta | 157 | 72,0% | 65,0% |
| media | 968 | 50,0% | 53,0% |
| baixa | 486 | 19,8% | 21,8% |

Leia a tabela assim: na faixa alta o modelo previu em média 72% e
65% das dívidas foram de fato recuperadas; na baixa, previu
20% e observou 22%. As faixas estão na ordem certa e
os números previstos acompanham os observados (a maior diferença é de
7 pontos percentuais, na faixa alta) — é isso que autoriza usar a
probabilidade no cálculo do retorno esperado. Se a faixa "alta" mostrasse taxa
observada parecida com a "média", o score não estaria separando nada, por
melhor que fosse o ROC-AUC.

Note também o tamanho das faixas: 60% das dívidas caem na faixa média.
O score separa bem os extremos e é honesto sobre o meio — não force faixas mais
"decididas" do que os dados permitem.

---

## Seção 9 — Serialização e versionamento (E3)

### `joblib`, e o pipeline inteiro

```python
joblib.dump(modelo_inadimplencia, MODELOS / "modelo_inadimplencia.joblib", compress=3)
joblib.dump(modelo_recuperabilidade, MODELOS / "modelo_recuperabilidade.joblib", compress=3)

for arquivo in sorted(MODELOS.glob("modelo_*.joblib")):
    print(f"{arquivo.name}: {arquivo.stat().st_size / 1024:.0f} KB")
```

O `joblib` é mais eficiente que o `pickle` para objetos com arrays NumPy, que é
o caso de modelos scikit-learn. O enunciado aceita `.pkl` ou `.joblib`; use
`.joblib`. O `compress=3` reduz bastante o arquivo sem custo perceptível.

**Salve o pipeline inteiro, nunca só o classificador:**

```python
# ERRADO -- joga fora o pré-processamento. Não copie.
joblib.dump(modelo_inadimplencia.named_steps["classificador"], "modelo.joblib")
```

Salvando só o classificador, quem carregar o modelo recebe um objeto que espera
dados já codificados e escalados — e não tem como saber como fazer isso. O
pipeline completo recebe o DataFrame bruto e cuida de tudo.

### Salve os metadados junto

Um `.joblib` sozinho não diz quando foi treinado, com qual versão do scikit-learn
nem o que esperava receber. Em seis meses, isso importa:

```python
def metadados_do_modelo(nome, modelo, alvo, n_treino, n_teste, metricas, extras=None):
    registro = {
        "nome": nome,
        "versao": "1.0.0",
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
        "algoritmo": type(modelo.named_steps["classificador"]).__name__,
        "alvo": alvo,
        "sklearn": sklearn.__version__,
        "python": platform.python_version(),
        "semente": SEMENTE,
        "split": {"tipo": "temporal", "corte_teste": str(CORTE_TESTE.date()),
                  "n_treino": int(n_treino), "n_teste": int(n_teste)},
        "atributos": {"categoricos": CATEGORICOS, "numericos": NUMERICOS},
        "fora_dos_atributos": sorted(PROIBIDOS),
        "metricas_teste": {k: (v if isinstance(v, list) else round(float(v), 4))
                           for k, v in metricas.items()},
        "dados": "carteira sintética calibrada — não representa a realidade fiscal",
    }
    registro.update(extras or {})
    return registro


registros = {
    "modelo_inadimplencia": metadados_do_modelo(
        "modelo_inadimplencia", modelo_inadimplencia, ALVO,
        len(treino), len(teste), metricas_inadimplencia,
        extras={"limiar_decisao": LIMIAR, "uso": "diagnóstico — não direciona cobrança"}),
    "modelo_recuperabilidade": metadados_do_modelo(
        "modelo_recuperabilidade", modelo_recuperabilidade, ALVO_REC,
        len(treino_rec), len(teste_rec), metricas_recuperabilidade,
        extras={"faixas": {"alta": ">= 0.66", "media": "0.33 a 0.66", "baixa": "< 0.33"},
                "uso": "ordenação da fila por retorno esperado"}),
}

for nome, registro in registros.items():
    with open(MODELOS / f"{nome}.json", "w", encoding="utf-8") as arquivo:
        json.dump(registro, arquivo, ensure_ascii=False, indent=2)
```

O limiar de decisão vai nos metadados porque **faz parte do modelo**: quem
carregar o `.joblib` e usar 0,5 por hábito estará usando outro classificador.

### Teste que o modelo salvo funciona

Esta célula é curta e evita a pior falha possível: entregar um arquivo que não
é o modelo.

```python
pares = [("modelo_inadimplencia", modelo_inadimplencia, X_teste),
         ("modelo_recuperabilidade", modelo_recuperabilidade, Xr_teste)]

for nome, original, X_amostra in pares:
    recarregado = joblib.load(MODELOS / f"{nome}.joblib")
    assert isinstance(recarregado, Pipeline), f"{nome}: o arquivo não contém um pipeline!"
    assert np.allclose(original.predict_proba(X_amostra.head(100))[:, 1],
                       recarregado.predict_proba(X_amostra.head(100))[:, 1]), f"{nome} divergiu!"
    print(f"{nome}: recarregado e verificado")
```

> **Só carregue arquivos `.joblib` e `.pkl` em que você confia.** Esses formatos
> executam código ao serem abertos. Um modelo baixado de fonte desconhecida pode
> rodar qualquer coisa na sua máquina. Carregue apenas o que a sua equipe gerou.

### Versionando em `/models`

Arquivos `.joblib` são binários — o Git não mostra diferenças entre versões, e
cada commit guarda uma cópia inteira. Com modelos pequenos isso é aceitável: os
dois desta trilha somam 5 KB. Então:

```bash
git add models/modelo_inadimplencia.joblib models/modelo_inadimplencia.json
git add models/modelo_recuperabilidade.joblib models/modelo_recuperabilidade.json
git commit -m "feat: modelos da Sprint 4 treinados com split temporal"
```

Confira que o `.gitignore` do projeto não está excluindo a pasta: o PoC ignora
`models/*.joblib` e `models/*.json` por padrão, e para o E3 você **precisa**
versionar. Adicione exceções:

```gitignore
!models/modelo_inadimplencia.joblib
!models/modelo_inadimplencia.json
!models/modelo_recuperabilidade.joblib
!models/modelo_recuperabilidade.json
```

Fique de olho no tamanho se trocar de algoritmo: o GitHub recusa arquivos acima
de 100 MB, e uma floresta sem limite de profundidade chega lá com facilidade.
Acima de ~50 MB, reduza o modelo ou use Git LFS.

---

## Checklist de entrega

**Reprodutibilidade**

- [ ] O notebook roda do início ao fim em kernel novo (*Restart & Run All*)
- [ ] As saídas estão salvas no `.ipynb` versionado
- [ ] A semente está fixa e as versões das bibliotecas registradas
- [ ] Nenhum caminho absoluto (`C:\Users\...`) — só caminhos relativos

**Metodologia (E1)**

- [ ] O grupo protegido foi excluído **antes** do split
- [ ] O split é temporal, com o corte explícito
- [ ] As verificações de vazamento (`assert`) estão no notebook e passam
- [ ] O eixo temporal é independente dos atributos preditivos
- [ ] Comparação, tunagem e limiar usam a validação temporal, não o teste
- [ ] Todo pré-processamento está dentro do `Pipeline`
- [ ] Os baselines (trivial, logística, árvore) estão no placar

**Modelos e métricas (E2)**

- [ ] Os **dois** modelos estão treinados: inadimplência e recuperabilidade
- [ ] Há um modelo com tunagem de hiperparâmetros no placar
- [ ] A escolha do vencedor segue uma regra declarada e está justificada
- [ ] Acurácia, precisão, recall, F1, ROC-AUC e matriz de confusão reportadas
- [ ] As métricas estão **interpretadas** no contexto do problema
- [ ] O limiar foi escolhido na validação, com a troca descrita em casos
- [ ] O conjunto de teste foi usado **uma única vez** por modelo
- [ ] O scoring produz as faixas alta/média/baixa, e a tabela de calibração confirma a ordem
- [ ] As métricas por subgrupo estão calculadas e salvas

**Artefatos (E3)**

- [ ] Os dois pipelines completos estão serializados em `/models`
- [ ] Os metadados em JSON acompanham cada modelo (com o limiar de decisão)
- [ ] O teste de recarga passa
- [ ] Os arquivos estão versionados no Git (confira o `.gitignore`)

**Ética**

- [ ] A natureza sintética dos dados está declarada na primeira célula
- [ ] A faixa de renda não é atributo preditivo
- [ ] As limitações do experimento estão escritas (eixo temporal sorteado, dados sintéticos)

---

## Os oito erros que a banca vai procurar

| Erro | Como aparece | Como evitar |
|---|---|---|
| 1. Split aleatório | `train_test_split(...)` sem eixo temporal | Corte por competência |
| 2. `fit` fora do pipeline | `StandardScaler().fit(X)` antes do split | Tudo dentro do `Pipeline` |
| 3. Validação embaralhada | `KFold` ou `cross_val_score` padrão na tunagem | `TimeSeriesSplit` sobre dados ordenados |
| 4. Teste usado várias vezes | Baselines, hiperparâmetros ou limiar decididos no teste | Tudo na validação; teste só no fim |
| 5. Coluna proibida nos atributos | Alvo, grupo protegido ou identificador em `X` | O `assert` da seção 4 |
| 6. Grupo protegido no treino | Exclusão feita depois do split, ou numa variável que ninguém usa | Excluir logo após a carga e seguir a partir de `universo` |
| 7. Arquivo que não é o modelo | Só o classificador salvo, ou uma variável sobrescrita | Salvar o pipeline e rodar o teste de recarga |
| 8. Métrica sem leitura | Tabela de números sem parágrafo de interpretação | Um parágrafo por resultado, com a troca em casos |

Os erros 6 e 7 não são hipotéticos: a primeira versão deste material cometia os
dois. A exclusão do IPTU Social vinha depois do split, e uma variável chamada
`melhor` guardava primeiro o modelo e depois um índice — o arquivo salvo
continha um número inteiro. Nenhum dos dois gerava mensagem de erro. Foram
encontrados executando a trilha de ponta a ponta, que é o que o primeiro item do
checklist pede.

---

## Onde olhar no PoC de referência

| Arquivo | Serve de modelo para | Ressalva |
|---|---|---|
| `src/modelo.py` | Pipeline, `ColumnTransformer`, serialização, exclusão do grupo protegido | **Usa split aleatório** — não copie essa parte |
| `src/fairness.py` | As métricas por subgrupo que a Sprint 5 vai pedir | — |
| `notebooks/eda_sprint2.ipynb` | Formato de notebook documentado | — |
| `tests/test_aula.py` | Como testar que uma trilha executa de ponta a ponta | — |

Copie o padrão, não o arquivo. A banca pergunta "por que vocês fizeram assim?",
e a resposta precisa ser sua.
