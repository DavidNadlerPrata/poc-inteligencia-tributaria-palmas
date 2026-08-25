# Como funciona

<p class="subtitulo">A metodologia por trás da ordenação da fila de cobrança, sem jargão técnico.</p>

---

## O que o sistema estima

Para cada débito inscrito em dívida ativa, o sistema estima **a probabilidade de
que ele seja recuperado nos próximos 12 meses**, e converte essa estimativa em
uma ordem de trabalho.

A conta é direta:

<div class="destaque">
<p style="font-size:1.1rem;margin:0"><strong>Retorno esperado = valor do débito × probabilidade de recuperação</strong></p>
</div>

Um débito de R$ 100 mil com 15% de chance tem retorno esperado de R$ 15 mil. Um
débito de R$ 20 mil com 80% de chance tem retorno esperado de R$ 16 mil. Para
efeito de programação do trabalho, o segundo vem primeiro — ainda que o primeiro
seja cinco vezes maior no papel.

---

## De onde vem a estimativa

O sistema examina o histórico de cobrança do município e identifica quais
características acompanharam os débitos efetivamente recuperados no passado.
Não há regra escrita à mão: os padrões são extraídos dos próprios registros.

### Os fatores que mais pesam

| Fator | Peso relativo | Direção |
|---|---|---|
| Tempo desde a inscrição em dívida ativa | Muito alto | Quanto mais antigo, menor a chance |
| Histórico de parcelamento | Médio | Quem já aderiu e cumpriu tende a aderir de novo |
| Valor consolidado do débito | Médio | Valores muito altos recuperam-se com menos frequência |
| Parcelamento rompido | Médio | Reduz a chance de forma significativa |
| Localização e características do imóvel | Baixo | Influência pequena |

O **tempo desde a inscrição domina** — pesa cerca de cinco vezes mais que o
segundo fator. Isso tem uma consequência de política de cobrança que independe
do sistema: **agir cedo importa mais do que qualquer refinamento de método**.
Um débito abordado no primeiro ano tem chance substancialmente maior de ser
recuperado que o mesmo débito abordado no quarto ano.

Vale notar o que *não* pesa: características do contribuinte e da região onde
mora têm influência pequena. O sistema aprendeu a olhar para o **processo de
cobrança**, não para o perfil da pessoa — e isso é intencional, como explicam as
[salvaguardas](salvaguardas.html).

---

## As três faixas

Para uso operacional, os débitos são agrupados em três faixas:

| Faixa | O que significa | Encaminhamento sugerido |
|---|---|---|
| **Alta recuperabilidade** | Chance estimada acima de 66% | Cobrança administrativa direta; oferta de parcelamento |
| **Média recuperabilidade** | Entre 33% e 66% | Análise caso a caso; campanhas segmentadas |
| **Baixa recuperabilidade** | Abaixo de 33% | Avaliar custo-benefício da diligência; considerar outras vias |

Na simulação, cerca de dois terços dos débitos caíram na faixa intermediária —
o que é esperado e honesto. O valor do sistema não está em resolver todos os
casos, mas em **separar com clareza os extremos**: os que vale a pena atacar
primeiro e os que provavelmente não compensam o custo da diligência.

---

## O que o sistema não faz

Esta seção é tão importante quanto as anteriores.

- **Não decide cobrar ninguém.** Produz uma fila; a decisão é do servidor.
- **Não altera valores devidos.** A estimativa não gera encargo, desconto ou
  qualquer efeito sobre o crédito tributário.
- **Não substitui a análise jurídica.** Prescrição, nulidades e demais questões
  processuais seguem o rito normal.
- **Não prevê o comportamento de uma pessoa.** Estima a frequência com que
  débitos de perfil semelhante foram recuperados no passado. É uma afirmação
  estatística sobre um conjunto, não um juízo sobre um indivíduo.
- **Não aponta sonegação, fraude ou má-fé.** Inadimplência e ilícito são coisas
  distintas, e o sistema não tem nem pretende ter competência sobre a segunda.

---

## Precisão: o que esperar

O sistema acerta consideravelmente mais que o acaso, e consideravelmente menos
que a perfeição. Na avaliação da prova de conceito, ele identificou corretamente
cerca de **70% dos débitos que de fato seriam recuperados**.

Isso significa que **ele erra** — e é importante que a expectativa esteja
calibrada. Um sistema desse tipo é útil porque melhora a média de uma operação
com milhares de casos, não porque acerta cada caso individual. É a mesma lógica
de uma triagem: ela ordena o atendimento, e o profissional decide.

Sistemas apresentados como quase infalíveis nesse domínio geralmente estão
medindo a si mesmos de forma incorreta.

---

## O painel de trabalho

A prova de conceito inclui um painel que apresenta:

- **Panorama da carteira** — volume, distribuição por região, arrecadação mensal
- **Fila priorizada** — ordenada por retorno esperado, com filtros por região e faixa
- **Consulta individual** — a estimativa de um débito específico e os fatores que a determinaram
- **Painel de equidade** — o acompanhamento do tratamento entre regiões da cidade

O painel é uma demonstração funcional e pode ser apresentado ao vivo em reunião
com a equipe da Sefin.
