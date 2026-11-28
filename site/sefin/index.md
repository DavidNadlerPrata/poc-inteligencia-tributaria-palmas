# Inteligência Tributária aplicada à dívida ativa

<p class="subtitulo">Como usar os próprios dados da Prefeitura para decidir por onde começar a cobrança — recuperando mais com a mesma equipe.</p>

<p class="creditos">Prova de conceito desenvolvida pela Universidade Federal do Tocantins<br>Bacharelado Interdisciplinar em Inteligência Artificial · Coordenação: Prof. Dr. David Nadler Prata</p>

---

## O problema

Palmas tem cerca de **R$ 894 milhões** inscritos em dívida ativa — R$ 363 milhões
de IPTU e R$ 380 milhões de ISS. São dezenas de milhares de débitos, e a equipe
de cobrança é a mesma independentemente do tamanho da carteira.

A pergunta prática não é *quem deve* — isso o cadastro já responde. A pergunta é
**por onde começar**: quais débitos, cobrados primeiro, trazem mais retorno para
o município.

Hoje essa ordenação costuma seguir o valor do débito. É um critério intuitivo,
mas ele concentra esforço justamente nas dívidas mais antigas e de maior valor —
que são também as menos recuperáveis. O resultado é uma equipe ocupada com casos
de baixa chance de êxito, enquanto débitos recentes e recuperáveis envelhecem na
fila.

---

## A proposta

Um sistema que ordena a fila de cobrança por **retorno esperado**: quanto se
espera efetivamente recuperar de cada débito, e não apenas quanto ele vale no
papel.

<div class="destaque">
<h3>A ideia em uma linha</h3>
<p>Um débito de R$ 50 mil com 10% de chance de recuperação vale menos, para a
programação do trabalho, que um débito de R$ 8 mil com 80% de chance. O sistema
calcula essa conta para toda a carteira e ordena a fila.</p>
</div>

Ordenar apenas pela chance de recuperação privilegiaria dívidas pequenas e
fáceis. Ordenar apenas pelo valor privilegiaria dívidas grandes e incobráveis.
O retorno esperado — valor multiplicado pela probabilidade — equilibra os dois.

---

## O que a prova de conceito demonstrou

<div class="cartoes">
<div class="cartao"><div class="valor">52%</div><div class="rotulo">do resultado alcançado ao trabalhar apenas os 20% melhores casos</div></div>
<div class="cartao"><div class="valor">82%</div><div class="rotulo">do resultado alcançado na metade da carteira</div></div>
<div class="cartao"><div class="valor">4 em 10</div><div class="rotulo">casos classificados em faixa de alta ou baixa recuperabilidade — os demais exigem análise</div></div>
</div>

O achado central é a **concentração**: o retorno não se distribui por igual pela
carteira. Uma parcela pequena dos débitos responde por uma fatia
desproporcional do que se consegue recuperar.

| Parcela da carteira trabalhada | Retorno alcançado |
|---|---|
| 10% dos casos | 34,3% |
| **20% dos casos** | **51,7%** |
| 30% dos casos | 64,2% |
| 50% dos casos | 81,9% |

Em termos operacionais: se a equipe consegue trabalhar bem um quinto da
carteira por ciclo, a diferença entre escolher esse quinto ao acaso e escolhê-lo
pelo retorno esperado é de **duas vezes e meia** no resultado.

### Comparado com uma regra simples

A comparação que importa não é com o acaso, e sim com o que a equipe faria sem
o sistema — por exemplo, cobrar primeiro as maiores dívidas. Medimos isso com o
valor **de fato recuperado** em dívidas que o sistema não usou no aprendizado:

| Trabalhando os 20% primeiros casos de cada fila | Valor recuperado alcançado |
|---|---|
| Fila do sistema | **47%** |
| Maiores dívidas primeiro | 44% |
| Ordem aleatória | 20% |

O sistema é melhor que a regra simples, mas por pouco: cerca de 4 pontos.
Quase todo o ganho vem de priorizar pelo valor. Por isso o piloto proposto
compara o sistema com o critério que a equipe já usa — se a diferença for
pequena também nos dados reais, uma regra simples pode bastar.

<div class="aviso">
<p><strong>Estes percentuais vêm de uma simulação, não de dados reais de contribuintes.</strong></p>
<p>A prova de conceito foi construída sobre uma carteira simulada, calibrada
pelos números oficiais publicados pela Sefin. O que ela demonstra é que o
<em>método</em> funciona e que o efeito de concentração é expressivo — não uma
previsão de quanto o município vai arrecadar. Os valores reais só podem ser
estimados com acesso aos dados de cadastro, mediante convênio.</p>
</div>

---

## Como o sistema chega ao resultado

O sistema aprende com o **histórico de cobrança do próprio município**: quais
débitos foram pagos, quais parcelamentos foram cumpridos, quanto tempo se passou
desde a inscrição em dívida ativa.

O fator que mais pesa na estimativa é o **tempo desde a inscrição** — pesa cinco
vezes mais que qualquer outro. Débitos recentes se recuperam com muito mais
frequência que débitos antigos, e essa relação é forte o bastante para orientar
sozinha boa parte da decisão.

Depois vêm o histórico de parcelamento (quem já aderiu e cumpriu tende a aderir
de novo), o valor consolidado e a existência de parcelamento rompido.

<p><a class="botao botao-primario" href="como-funciona.html">Ver a metodologia em detalhe</a></p>

---

## Decisão assistida, nunca automática

O sistema **não decide** cobrar ninguém. Ele produz uma fila de trabalho
ordenada, e a decisão sobre cada caso continua sendo do servidor responsável.

Essa não é uma formalidade jurídica: é uma escolha de projeto. Um sistema
preditivo acerta na média e erra no caso particular. Quem tem competência legal
e conhecimento do contexto para decidir sobre um contribuinte específico é o
servidor — o sistema apenas organiza por onde ele começa.

---

## Salvaguardas

A aplicação de inteligência artificial à cobrança tributária levanta questões
legítimas. A prova de conceito as tratou explicitamente:

- **Beneficiários do IPTU Social ficam fora do sistema.** Idosos, aposentados,
  pensionistas e pessoas com deficiência de baixa renda são excluídos de toda
  ação preditiva de cobrança — por construção, não por procedimento.
- **O sistema foi auditado quanto ao tratamento entre regiões da cidade.** Sem
  ajuste, a diferença de tratamento entre setores de renda alta, média e baixa
  passou do limite técnico adotado; com o ajuste por região, publicado e
  verificável, ficou abaixo dele.
- **Nenhum dado pessoal foi utilizado** na construção desta prova de conceito.
- **Todo contribuinte pode contestar** sua classificação e obter revisão humana,
  conforme o Art. 20 da Lei Geral de Proteção de Dados.

<p><a class="botao botao-secundario" href="salvaguardas.html">Ver as salvaguardas em detalhe</a></p>

---

## Próximos passos

A prova de conceito está pronta e demonstrável. Para transformá-la em ferramenta
operacional, o passo seguinte é um **piloto com dados reais**, o que exige
convênio formal entre a Prefeitura e a UFT.

<p><a class="botao botao-primario" href="implantacao.html">Ver o roteiro de implantação</a></p>
