# Aula — Sprint 4, E3: notebook documentado e modelo serializado

Material de apoio para o entregável **E3** da Sprint 4 (Módulo 6 — Introdução à
Inteligência Artificial): *"Notebook Jupyter com a trilha completa (EDA →
pré-processamento → treinamento → avaliação) e o modelo salvo (.pkl/.joblib)
versionado em /models."*

---

## Antes de começar: o E3 não é só o arquivo

O E3 vale 15% da rubrica, mas é ele que **carrega** o E1 (metodologia, 25%) e o
E2 (modelos e métricas, 30%). O notebook é onde a banca vai verificar se o
split temporal está correto e se as métricas foram interpretadas — ou seja,
70% da nota da sprint passa por este arquivo.

Então o critério não é "o notebook roda". É:

> Alguém que não participou do projeto consegue abrir o notebook, entender cada
> decisão, executá-lo do início ao fim e obter os mesmos números?

Se a resposta for sim, o E3 está pronto.

---

## A estrutura: oito seções

Monte o notebook nesta ordem. Ela não é arbitrária — cada seção depende da
anterior, e inverter duas delas é exatamente como se cria vazamento de dados.

| # | Seção | Entregável |
|---|---|---|
| 1 | Cabeçalho e proveniência dos dados | E3 |
| 2 | Análise exploratória orientada a decisão | E3 |
| 3 | **Split temporal** | **E1** |
| 4 | Pré-processamento dentro do pipeline | E1 |
| 5 | Modelos baseline | E1 |
| 6 | Modelo final e tunagem | E2 |
| 7 | Avaliação e métricas por subgrupo | E2 |
| 8 | Serialização e versionamento | E3 |

---

## Seção 1 — Cabeçalho e proveniência

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

Ainda nesta seção, fixe a semente e registre as versões:

```python
import platform
import joblib, numpy as np, pandas as pd, sklearn

SEMENTE = 42
np.random.seed(SEMENTE)

print(f"python  {platform.python_version()}")
print(f"pandas  {pd.__version__}")
print(f"sklearn {sklearn.__version__}")
print(f"joblib  {joblib.__version__}")
```

Sem isso, "não reproduz na minha máquina" vira discussão sem dados.

---

## Seção 2 — EDA orientada a decisão

Você já fez a análise exploratória na Sprint 2. **Não repita aqui.** Esta seção
é curta e tem um único propósito: mostrar os fatos que justificam as decisões de
modelagem que vêm a seguir.

Para cada gráfico ou tabela, pergunte: *que decisão isto sustenta?* Se não
sustenta nenhuma, tire do notebook.

O que vale incluir:

```python
# 1) Balanceamento do alvo -- decide se precisa de class_weight
print(dados["divida_recuperada_12m"].value_counts(normalize=True))

# 2) Volume útil -- o modelo de recuperabilidade só vale para quem tem dívida
com_divida = dados[dados["valor_divida_consolidada"] > 0]
print(f"universo: {len(com_divida)} de {len(dados)} registros")

# 3) Grupos protegidos -- quantos saem antes do treino
print(f"IPTU Social (excluídos): {dados['iptu_social'].sum()}")
```

Feche a seção com uma célula Markdown listando as decisões tomadas. Exemplo:

> **Decisões que a EDA sustenta**
> 1. O alvo está equilibrado (≈50/50) → não usaremos reamostragem.
> 2. O modelo de recuperabilidade usa só os ~16 mil registros com dívida inscrita.
> 3. Os beneficiários do IPTU Social saem antes de qualquer treino.

---

## Seção 3 — Split temporal (o coração do E1)

Esta é a seção mais importante do notebook e a que a banca vai atacar primeiro.
O enunciado avisa: *"nada do futuro pode informar o passado no treino — a banca
vai perguntar."*

### 3.1 Por que `train_test_split` aleatório reprova aqui

```python
# ERRADO para este problema
from sklearn.model_selection import train_test_split
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y)
```

O split aleatório mistura períodos: o modelo treina com dados de 2026 e é
testado em dados de 2024. Na operação real isso é impossível — você só tem o
passado para prever o futuro. Um split aleatório **superestima** o desempenho,
porque o modelo viu padrões de um período que, na vida real, ainda não existiria.

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
# ARMADILHA -- parece razoável e produz um split inútil
dados["data_inscricao"] = HOJE - pd.to_timedelta(dados["tempo_inadimplencia_dias"], unit="D")
```

Medimos o resultado disso:

| Conjunto | Tempo médio de inadimplência | Taxa de recuperação |
|---|---|---|
| treino (80% mais antigo) | 1.057 dias | 47,8% |
| teste (20% mais recente) | 216 dias | 66,8% |

O corte temporal passou a separar **exatamente pelo preditor dominante**. O
teste ficou só com dívidas recentes, cuja taxa de recuperação é muito maior. As
distribuições são incomparáveis, e qualquer métrica calculada ali é enganosa.

**A lição geral:** o eixo temporal precisa ser **independente** dos atributos
preditivos. Se o seu "tempo" é função de uma feature, não é um eixo temporal —
é a própria feature disfarçada.

### 3.3 O eixo temporal correto: competência do registro

No dado real, a dívida ativa é uma **foto mensal**: cada registro diz como o
contribuinte estava em determinado mês de competência. É esse campo que define o
eixo temporal.

Se sua base não tem, acrescente ao gerador um mês de competência independente:

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(SEMENTE)

# Competência: mês de referência do registro. Independente de qualquer atributo.
meses = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
dados["competencia"] = rng.choice(meses, size=len(dados))
```

Documente essa escolha no notebook. Inventar um eixo temporal é aceitável em
PoC — **esconder que você inventou, não é**.

### 3.4 Fazendo o corte

```python
CORTE = pd.Timestamp("2026-04-01")      # últimos ~6 meses para teste

treino = com_divida[com_divida["competencia"] <  CORTE]
teste  = com_divida[com_divida["competencia"] >= CORTE]

print(f"treino: {len(treino):5d} ({len(treino)/len(com_divida):.0%})"
      f" | até {treino['competencia'].max().date()}")
print(f"teste:  {len(teste):5d} ({len(teste)/len(com_divida):.0%})"
      f" | de {teste['competencia'].min().date()}")
```

Resultado esperado com esta base: 80% treino / 20% teste.

### 3.5 Provando que não há vazamento

Não afirme que não há vazamento: **demonstre**. Três verificações, em código, no
notebook:

```python
# 1) Não há sobreposição temporal
assert treino["competencia"].max() < teste["competencia"].min(), "sobreposição temporal!"

# 2) O mesmo contribuinte não está nos dois lados
vazados = set(treino["id_contribuinte"]) & set(teste["id_contribuinte"])
assert not vazados, f"{len(vazados)} contribuintes em treino e teste"

# 3) As distribuições são comparáveis (se não forem, o corte está ruim)
comparacao = pd.DataFrame({
    "treino": treino[["tempo_inadimplencia_dias", "valor_divida_consolidada",
                      "divida_recuperada_12m"]].mean(),
    "teste":  teste[["tempo_inadimplencia_dias", "valor_divida_consolidada",
                     "divida_recuperada_12m"]].mean(),
})
print(comparacao)
```

Com o eixo de competência, a comparação fica assim — e é isso que você quer ver:

| Métrica | Treino | Teste |
|---|---|---|
| Tempo de inadimplência (dias) | 886 | 903 |
| Dívida média (R$) | 3.931 | 3.926 |
| Taxa de recuperação | 51,9% | 50,5% |

Esses `assert` são o seu seguro na banca. Quando perguntarem sobre vazamento,
você rola até a célula e mostra a verificação rodando.

### 3.6 E a validação?

O enunciado pede treino/teste/**validação**. Com eixo temporal, a validação sai
de dentro do treino, respeitando a ordem:

```python
from sklearn.model_selection import TimeSeriesSplit

# 4 dobras: cada uma treina no passado e valida no futuro imediato
validacao_temporal = TimeSeriesSplit(n_splits=4)
```

Use isso na tunagem (seção 6) — **nunca** `KFold` ou `cross_val_score` com
embaralhamento, que recriam o vazamento que você acabou de eliminar.

> **Ordene antes de usar `TimeSeriesSplit`.** Ele divide por posição na tabela,
> não por data. Se as linhas não estiverem em ordem cronológica, as dobras
> ficam embaralhadas e a proteção se perde:
> ```python
> treino = treino.sort_values("competencia").reset_index(drop=True)
> ```

---

## Seção 4 — Pré-processamento dentro do pipeline

### O erro que mais reprova

```python
# ERRADO -- vazamento silencioso
from sklearn.preprocessing import StandardScaler
escalador = StandardScaler().fit(X)        # <-- viu treino E teste
X_tr = escalador.transform(X_tr)
X_te = escalador.transform(X_te)
```

O `fit` calculou média e desvio usando **o conjunto de teste inteiro**.
Informação do teste vazou para o treino, e a métrica final fica otimista. Não dá
erro, não dá aviso — e é uma das primeiras coisas que a banca procura.

### A forma correta: tudo dentro de um `Pipeline`

```python
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

CATEGORICOS = ["tipo_imovel", "setor_urbano"]
NUMERICOS = ["area_construida_m2", "valor_venal", "valor_iptu_anual",
             "distancia_centro_km", "exercicios_inadimplentes_5a",
             "tempo_inadimplencia_dias", "valor_divida_consolidada",
             "qtd_parcelamentos_anteriores", "parcelamento_rompido",
             "qtd_notificacoes"]

preparo = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICOS),
    ("num", Pipeline([
        ("imputacao", SimpleImputer(strategy="median")),
        ("escala", StandardScaler()),
    ]), NUMERICOS),
])

modelo = Pipeline([("preparo", preparo), ("classificador", ...)])
modelo.fit(X_treino, y_treino)      # o fit acontece SÓ no treino
```

Por que isso resolve: o `Pipeline` só faz `fit` no que você passar para ele.
Durante a validação cruzada, ele refaz o `fit` em cada dobra automaticamente.
Você não consegue vazar por descuido.

**`handle_unknown="ignore"` não é opcional** com split temporal: pode aparecer
no teste uma categoria que não existia no treino (um setor novo). Sem isso, o
notebook quebra na hora da avaliação.

### Duas colunas que NÃO entram como atributo

```python
# faixa_renda_setor -> só para auditoria de fairness (Sprint 5)
# iptu_social       -> dado sensível, usado só para EXCLUIR
```

A primeira é o grupo protegido: usá-la como preditor é discriminação direta por
renda. A segunda é dado sensível (LGPD, Art. 5º, II) e serve apenas para remover
o contribuinte do universo:

```python
universo = dados[dados["iptu_social"] == 0].copy()
print(f"excluídos pelo IPTU Social: {len(dados) - len(universo)}")
```

---

## Seção 5 — Baselines (E1)

O enunciado pede explicitamente **Regressão Logística e Árvore de Decisão** como
referência. Baseline não é formalidade: é o número que dá sentido ao resultado
final. Um Random Forest com ROC-AUC 0,67 é bom ou ruim? Só o baseline responde.

```python
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score, f1_score

candidatos = {
    "trivial (maioria)": DummyClassifier(strategy="most_frequent"),
    "regressão logística": LogisticRegression(max_iter=1000, random_state=SEMENTE),
    "árvore de decisão": DecisionTreeClassifier(max_depth=5, random_state=SEMENTE),
}

resultados = []
for nome, estimador in candidatos.items():
    modelo = Pipeline([("preparo", preparo), ("classificador", estimador)])
    modelo.fit(X_treino, y_treino)
    previsto = modelo.predict(X_teste)
    try:
        prob = modelo.predict_proba(X_teste)[:, 1]
        auc = roc_auc_score(y_teste, prob)
    except (AttributeError, ValueError):
        auc = float("nan")          # o classificador trivial não tem AUC útil
    resultados.append({"modelo": nome, "f1": f1_score(y_teste, previsto, zero_division=0),
                       "roc_auc": auc})

pd.DataFrame(resultados).round(4)
```

Inclua o **classificador trivial**. Se o seu modelo sofisticado não superar
"chutar sempre a classe majoritária", isso precisa aparecer no notebook — e é
melhor você descobrir antes da banca.

### Quando o classificador trivial parece ganhar

Rodando essa comparação nesta base, o resultado foi:

| Modelo | F1 | ROC-AUC |
|---|---|---|
| trivial (maioria) | **0,6700** | 0,5000 |
| regressão logística | 0,6502 | 0,6676 |
| árvore de decisão | 0,6596 | 0,6455 |
| Random Forest tunado | 0,6524 | 0,6596 |

Leia de novo: **o classificador trivial teve o melhor F1 de todos**. Se você
reportar só o F1, a conclusão é que nenhum modelo serviu — e ela estaria errada.

**Por que isso acontece.** O alvo está em 50,4% no conjunto de teste. Chutando
sempre "1", o recall vira 1,0 e a precisão vira 0,504, o que dá
F1 = 2 × 0,504 / (0,504 + 1) = **0,670** sem aprender absolutamente nada. Já o
ROC-AUC do trivial é 0,500: ele não ordena os casos, porque atribui a mesma
previsão a todos.

**O que distingue os dois.** F1 depende do limiar escolhido; ROC-AUC não. Um
modelo pode ordenar bem os casos (ROC-AUC alto) e ainda assim ter F1 ruim porque
o corte em 0,5 está no lugar errado para a distribuição dos scores. Medindo o F1
do Random Forest em vários limiares:

| Limiar | F1 | Precisão | Recall |
|---|---|---|---|
| 0,35 | 0,6873 | 0,532 | 0,970 |
| **0,40** | **0,6949** | 0,560 | 0,914 |
| 0,45 | 0,6805 | 0,580 | 0,824 |
| 0,50 | 0,6524 | 0,593 | 0,725 |
| 0,55 | 0,5970 | 0,610 | 0,585 |

Em 0,40 o F1 chega a **0,695** e supera o trivial com folga. O modelo sempre foi
melhor — o limiar padrão é que escondia isso.

**Três conclusões para o notebook:**

1. **Compare modelos por ROC-AUC**, que não depende de limiar. Use F1 para
   avaliar uma configuração de decisão específica.
2. **O limiar é uma decisão de projeto**, não uma constante da biblioteca.
   Escolha-o pelo custo do erro no seu problema (seção 7) e **documente a
   escolha**.
3. **Reporte o trivial mesmo quando ele parece ganhar**, com a explicação acima.
   Mostrar que você entende por que o F1 dele é alto vale mais que esconder a
   linha.

---

## Seção 6 — Modelo final e tunagem (E2)

### Justifique a escolha com base na EDA

O enunciado cobra *"justificativa das escolhas algorítmicas"*. Não escreva "usamos
Random Forest porque é bom". Argumente a partir dos seus dados:

> **Por que gradient boosting.** Os atributos misturam escalas muito diferentes
> (reais, dias, contagens) com categóricas de baixa cardinalidade, e as relações
> são não lineares — o efeito do tempo de inadimplência satura. Árvores
> impulsionadas lidam com isso sem exigir normalização, toleram os outliers de
> valor venal vistos na EDA e fornecem importância de atributos, que sustenta o
> direito à explicação do Art. 20 da LGPD. A regressão logística foi testada
> como baseline e perdeu desempenho nas interações; redes neurais foram
> descartadas por opacidade desnecessária neste volume de dados.

### Tunagem com validação temporal

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV

modelo = Pipeline([
    ("preparo", preparo),
    ("classificador", RandomForestClassifier(random_state=SEMENTE, n_jobs=-1)),
])

grade = {
    "classificador__n_estimators": [200, 400],
    "classificador__max_depth": [6, 10, None],
    "classificador__min_samples_leaf": [1, 5, 20],
}

busca = GridSearchCV(
    modelo, grade,
    cv=TimeSeriesSplit(n_splits=4),     # <-- temporal, não KFold
    scoring="roc_auc",
    n_jobs=-1, verbose=1,
)
busca.fit(X_treino, y_treino)           # <-- só o treino; o teste nem aparece

print("melhores parâmetros:", busca.best_params_)
print(f"ROC-AUC na validação: {busca.best_score_:.4f}")
melhor = busca.best_estimator_
```

Note o prefixo `classificador__`: dentro de um `Pipeline`, os parâmetros são
endereçados pelo nome do passo com dois sublinhados.

**O conjunto de teste não aparece em nenhum lugar desta seção.** Ele é usado uma
única vez, na seção 7. Se você ajustar hiperparâmetros olhando o resultado do
teste, ele deixa de ser teste e vira validação — e a métrica final perde valor.

### O segundo modelo: scoring de recuperabilidade

O E2 pede dois modelos. O segundo estima a probabilidade de recuperação e a
converte nas faixas pedidas:

```python
def faixa_recuperabilidade(probabilidade):
    """Traduz o score contínuo nas faixas exigidas pelo enunciado."""
    if probabilidade >= 0.66:
        return "alta"
    if probabilidade >= 0.33:
        return "media"
    return "baixa"

teste = teste.copy()
teste["prob_recuperacao"] = melhor.predict_proba(X_teste)[:, 1]
teste["faixa"] = teste["prob_recuperacao"].map(faixa_recuperabilidade)

# O que o MVP (E4) vai ordenar: retorno esperado
teste["retorno_esperado"] = (teste["valor_divida_consolidada"]
                             * teste["prob_recuperacao"]).round(2)

print(teste["faixa"].value_counts())
```

---

## Seção 7 — Avaliação e métricas por subgrupo

### Métricas completas

O enunciado exige acurácia, precisão, recall, F1 **e** matriz de confusão:

```python
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, precision_score, recall_score,
                             f1_score, roc_auc_score)

prob = melhor.predict_proba(X_teste)[:, 1]
previsto = (prob >= 0.5).astype(int)

metricas = {
    "acuracia": accuracy_score(y_teste, previsto),
    "precisao": precision_score(y_teste, previsto, zero_division=0),
    "recall": recall_score(y_teste, previsto, zero_division=0),
    "f1": f1_score(y_teste, previsto, zero_division=0),
    "roc_auc": roc_auc_score(y_teste, prob),
}
print({k: round(v, 4) for k, v in metricas.items()})
print(confusion_matrix(y_teste, previsto))
print(classification_report(y_teste, previsto, zero_division=0))
```

### Interprete, não só reporte

A rubrica diz *"métricas completas e interpretadas"*. Uma tabela de números sem
leitura não cumpre o critério. Para cada métrica, diga o que ela significa **no
problema**:

> A matriz de confusão mostra 598 falsos negativos: 598 dívidas recuperáveis que
> o modelo deixaria de priorizar — dinheiro abandonado na fila. Os 863 falsos
> positivos custam diligências sem retorno. Como o custo de uma diligência
> perdida é muito menor que o de abandonar crédito recuperável, mantivemos o
> limiar em 0,5, que privilegia recall (0,698) sobre precisão (0,616).

E seja honesto com números modestos:

> ROC-AUC de 0,67 indica desempenho moderado: o modelo é claramente melhor que o
> acaso e erra com frequência. Isso é esperado, já que o processo gerador embute
> ruído deliberado. Valores próximos de 1,0 aqui indicariam vazamento, não
> qualidade.

### Escolha o limiar pelo custo do erro

Como vimos na seção 5, o limiar de 0,5 é só o padrão da biblioteca — não é uma
escolha fundamentada. Faça a sua, e registre o raciocínio:

```python
from sklearn.metrics import precision_recall_curve

precisoes, recalls, limiares = precision_recall_curve(y_teste, prob)
f1_por_limiar = 2 * precisoes * recalls / (precisoes + recalls + 1e-12)
melhor = int(np.nanargmax(f1_por_limiar))

print(f"limiar que maximiza F1: {limiares[melhor]:.3f} (F1 = {f1_por_limiar[melhor]:.4f})")
```

Mas atenção: **maximizar F1 não é automaticamente o certo**. O F1 trata falso
positivo e falso negativo como igualmente ruins, e no seu problema eles não são:

> **Nossa escolha de limiar.** Um falso positivo custa uma diligência sem
> retorno; um falso negativo abandona crédito recuperável. Como o segundo custa
> mais à Prefeitura, adotamos o limiar 0,40, que eleva o recall de 0,725 para
> 0,914 ao custo de reduzir a precisão de 0,593 para 0,560. Em números
> absolutos, as dívidas recuperáveis identificadas sobem de 1.126 para 1.421 —
> **295 casos a mais na fila** —, ao preço de diligências adicionais sem êxito.

> **Reporte o ganho em casos, não só em pontos de métrica.** "Recall subiu 0,19"
> não significa nada para a Sefin; "295 dívidas recuperáveis que entrariam na
> fila" significa. A conversão de métrica em efeito é o que a rubrica chama de
> interpretar.

Esse parágrafo — com os números concretos da troca — é o tipo de interpretação
que a rubrica do E2 está cobrando.

### Métricas por subgrupo — guarde isto para a Sprint 5

O enunciado é explícito: *"Guardem as métricas POR SUBGRUPO (faixa de renda,
região): a Sprint 5 fará a análise de fairness sobre elas."*

```python
avaliacao = X_teste.copy()
avaliacao["y_real"] = y_teste.to_numpy()
avaliacao["y_prob"] = prob
avaliacao["y_pred"] = previsto
avaliacao["faixa_renda_setor"] = teste["faixa_renda_setor"].to_numpy()   # grupo protegido

def metricas_por_grupo(df, coluna):
    linhas = []
    for grupo, bloco in df.groupby(coluna):
        real, pred = bloco["y_real"].to_numpy(), bloco["y_pred"].to_numpy()
        positivos = real == 1
        linhas.append({
            "grupo": grupo, "n": len(bloco),
            "prevalencia": real.mean(),
            "taxa_selecao": pred.mean(),
            "recall": pred[positivos].mean() if positivos.any() else np.nan,
            "precisao": real[pred == 1].mean() if (pred == 1).any() else np.nan,
        })
    return pd.DataFrame(linhas).round(4)

por_renda = metricas_por_grupo(avaliacao, "faixa_renda_setor")
print(por_renda)

# Salve: a Sprint 5 vai consumir este arquivo
avaliacao.to_csv("../data/avaliacao_teste.csv", sep=";", index=False)
por_renda.to_csv("../data/metricas_por_subgrupo.csv", sep=";", index=False)
```

Salvar o conjunto de teste com as predições é o que permite auditar fairness na
Sprint 5 **sem retreinar nada**. Equipe que não salva isso retrabalha depois.

---

## Seção 8 — Serialização e versionamento (E3)

### `joblib`, não `pickle`

```python
import joblib
from pathlib import Path

MODELOS = Path("../models")
MODELOS.mkdir(exist_ok=True)

joblib.dump(melhor, MODELOS / "modelo_recuperabilidade.joblib")
```

O `joblib` é mais eficiente que o `pickle` para objetos com arrays NumPy, que é
exatamente o caso de modelos scikit-learn. O enunciado aceita `.pkl` ou
`.joblib`; use `.joblib`.

### Salve o pipeline inteiro, nunca só o classificador

```python
# ERRADO -- joga fora o pré-processamento
joblib.dump(melhor.named_steps["classificador"], "modelo.joblib")

# CORRETO -- o objeto completo
joblib.dump(melhor, "modelo.joblib")
```

Salvando só o classificador, quem carregar o modelo recebe um objeto que espera
dados já codificados e escalados — e não tem como saber como fazer isso. O
pipeline completo recebe o DataFrame bruto e cuida de tudo.

### Salve os metadados junto

Um `.joblib` sozinho não diz quando foi treinado, com qual versão do scikit-learn
nem o que esperava receber. Em seis meses, isso importa:

```python
import json
from datetime import datetime

metadados = {
    "nome": "modelo_recuperabilidade",
    "versao": "1.0.0",
    "treinado_em": datetime.now().isoformat(timespec="seconds"),
    "algoritmo": type(melhor.named_steps["classificador"]).__name__,
    "hiperparametros": busca.best_params_,
    "sklearn": sklearn.__version__,
    "python": platform.python_version(),
    "semente": SEMENTE,
    "split": {
        "tipo": "temporal",
        "corte": str(CORTE.date()),
        "n_treino": int(len(treino)),
        "n_teste": int(len(teste)),
    },
    "atributos": {"categoricos": CATEGORICOS, "numericos": NUMERICOS},
    "excluidos_do_treino": ["faixa_renda_setor (grupo protegido)",
                            "iptu_social (dado sensível, usado para excluir)"],
    "metricas_teste": {k: round(v, 4) for k, v in metricas.items()},
    "dados": "carteira sintética calibrada — não representa a realidade fiscal",
}

with open(MODELOS / "modelo_recuperabilidade.json", "w", encoding="utf-8") as f:
    json.dump(metadados, f, ensure_ascii=False, indent=2)
```

### Teste que o modelo salvo funciona

Esta célula é curta e evita a pior falha possível: entregar um arquivo corrompido.

```python
recarregado = joblib.load(MODELOS / "modelo_recuperabilidade.joblib")

prob_original = melhor.predict_proba(X_teste.head(100))[:, 1]
prob_recarregada = recarregado.predict_proba(X_teste.head(100))[:, 1]

assert np.allclose(prob_original, prob_recarregada), "o modelo salvo divergiu!"
print("modelo recarregado e verificado: predições idênticas")
```

### Versionando em `/models`

Arquivos `.joblib` são binários — o Git não consegue mostrar diferenças entre
versões, e cada commit guarda uma cópia inteira. Com modelos pequenos (os deste
PoC têm ~170 KB) isso é aceitável. Então:

```bash
git add models/modelo_recuperabilidade.joblib models/modelo_recuperabilidade.json
git commit -m "feat: modelo de recuperabilidade treinado com split temporal

ROC-AUC 0,67 no conjunto de teste (competências a partir de 2026-04).
Metadados e métricas por subgrupo em models/."
```

Confira que o `.gitignore` do projeto não está excluindo a pasta: o PoC ignora
`models/*.joblib` por padrão, e para o E3 você **precisa** versionar. Adicione
uma exceção:

```gitignore
!models/modelo_recuperabilidade.joblib
!models/modelo_recuperabilidade.json
```

Se o modelo passar de ~50 MB, use Git LFS em vez de commitar direto.

---

## Checklist de entrega

**Reprodutibilidade**

- [ ] O notebook roda do início ao fim em kernel novo (*Restart & Run All*)
- [ ] As saídas estão salvas no `.ipynb` versionado
- [ ] A semente está fixa e as versões das bibliotecas registradas
- [ ] Nenhum caminho absoluto (`C:\Users\...`) — só caminhos relativos

**Metodologia (E1)**

- [ ] O split é temporal, com o corte explícito
- [ ] Os três `assert` de vazamento estão no notebook e passam
- [ ] O eixo temporal é independente dos atributos preditivos
- [ ] A tunagem usa `TimeSeriesSplit`, não `KFold`
- [ ] Todo pré-processamento está dentro do `Pipeline`
- [ ] Os baselines (trivial, logística, árvore) estão treinados e comparados

**Modelos e métricas (E2)**

- [ ] A escolha algorítmica está justificada a partir da EDA
- [ ] Acurácia, precisão, recall, F1, ROC-AUC e matriz de confusão reportadas
- [ ] As métricas estão **interpretadas** no contexto do problema
- [ ] O conjunto de teste foi usado **uma única vez**
- [ ] O scoring de recuperabilidade produz as faixas alta/média/baixa
- [ ] As métricas por subgrupo estão calculadas e salvas

**Artefatos (E3)**

- [ ] O pipeline completo está serializado em `/models`
- [ ] Os metadados em JSON acompanham o modelo
- [ ] O teste de recarga passa
- [ ] Os arquivos estão versionados no Git (confira o `.gitignore`)

**Ética**

- [ ] A natureza sintética dos dados está declarada na primeira célula
- [ ] Os beneficiários do IPTU Social foram excluídos antes do treino
- [ ] A faixa de renda não é atributo preditivo

---

## Os sete erros que a banca vai procurar

| Erro | Como aparece | Como evitar |
|---|---|---|
| 1. Split aleatório | `train_test_split(...)` sem eixo temporal | Corte por competência |
| 2. `fit` fora do pipeline | `StandardScaler().fit(X)` antes do split | Tudo dentro do `Pipeline` |
| 3. Validação embaralhada | `KFold` ou `cross_val_score` padrão na tunagem | `TimeSeriesSplit` |
| 4. Teste usado várias vezes | Hiperparâmetros ajustados olhando o teste | Validação sai do treino |
| 5. Alvo entre os preditores | `divida_recuperada_12m` na lista de atributos | Revise `X.columns` |
| 6. Só o classificador salvo | `dump(pipeline.named_steps[...])` | Salve o pipeline inteiro |
| 7. Métrica sem leitura | Tabela de números sem parágrafo de interpretação | Um parágrafo por métrica |

O erro 5 merece um teste explícito, porque é silencioso e infla a métrica para
perto de 1,0:

```python
ALVOS = {"divida_recuperada_12m", "inadimplente_proximo_exercicio"}
assert not (ALVOS & set(X_treino.columns)), "vazamento: alvo entre os atributos!"
```

---

## Onde olhar no PoC de referência

| Arquivo | Serve de modelo para | Ressalva |
|---|---|---|
| `src/modelo.py` | Pipeline, `ColumnTransformer`, serialização, exclusão do grupo protegido | **Usa split aleatório** — não copie essa parte |
| `src/fairness.py` | As métricas por subgrupo que a Sprint 5 vai pedir | — |
| `notebooks/eda_sprint2.ipynb` | Formato de notebook documentado | — |

Copie o padrão, não o arquivo. A banca pergunta "por que vocês fizeram assim?",
e a resposta precisa ser sua.
