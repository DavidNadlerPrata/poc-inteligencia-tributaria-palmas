# Roteiro de implantação

<p class="subtitulo">O que existe hoje, o que falta, e o que é necessário da Prefeitura para avançar.</p>

---

## Situação atual

A prova de conceito está **completa e demonstrável**. O caminho inteiro funciona
de ponta a ponta: coleta de dados, organização em banco, estimativa de
recuperabilidade, ordenação da fila, auditoria de equidade e painel de trabalho.

O que ela **não** tem é acesso aos dados reais de cadastro — e essa é
precisamente a fronteira entre demonstração e ferramenta operacional.

<div class="aviso">
<p><strong>O obstáculo não é técnico.</strong> O sistema está construído. O que falta é o
acesso aos dados de dívida ativa individualizados, que são protegidos por lei e
só podem ser compartilhados mediante instrumento formal.</p>
</div>

---

## Os dados necessários

Para um piloto, seriam necessários os campos abaixo — **sem nome, CPF ou
endereço**, que não entram no processamento:

| Informação | Para que serve |
|---|---|
| Identificador do débito (pseudonimizado) | Vincular o resultado ao caso, sem identificar a pessoa |
| Data de inscrição em dívida ativa | Fator de maior peso na estimativa |
| Valor consolidado | Cálculo do retorno esperado |
| Tributo de origem (IPTU, ISS, ITBI, taxas) | Segmentação |
| Histórico de parcelamento e situação | Segundo fator de maior peso |
| Situação atual (pago, parcelado, em aberto) | Referência de aprendizado |
| Setor urbano ou região | Auditoria de equidade |
| Marcação de IPTU Social | Exclusão obrigatória |

Um histórico de **três a cinco anos** é suficiente. Quanto mais longo, melhor a
estimativa — mas o sistema já produz resultado útil com três.

---

## Fases sugeridas

### Fase 1 — Convênio e acesso aos dados

Instrumento formal entre a Prefeitura e a UFT, definindo finalidade, base legal,
responsabilidades e prazo de retenção. Envolvimento do encarregado de dados
(DPO) do município e da Procuradoria.

*Produto: convênio assinado e extração de dados disponível em ambiente controlado.*

### Fase 2 — Recalibração com dados reais

O sistema é retreinado sobre o histórico real de cobrança do município. As
estimativas de desempenho e a auditoria de equidade são refeitas — os números
apresentados hoje valem para a simulação e serão substituídos pelos reais.

*Produto: relatório de desempenho e auditoria com dados de Palmas.*

### Fase 3 — Piloto controlado

Aplicação a um recorte da carteira — por exemplo, IPTU de um conjunto de setores
— com **grupo de comparação**: parte da carteira trabalhada pelo critério atual,
parte pela fila priorizada.

Esta fase é a que responde à pergunta que realmente importa: *quanto a mais se
recupera com o novo critério?* Sem grupo de comparação, qualquer variação pode
ser atribuída a sazonalidade ou a outros fatores.

*Produto: medição comparada de recuperação entre os dois critérios.*

### Fase 4 — Avaliação e decisão

Com o resultado do piloto em mãos, a Sefin decide sobre a ampliação. A prova de
conceito não pressupõe essa decisão: se o ganho medido não justificar a adoção,
o resultado do piloto terá sido igualmente valioso.

*Produto: relatório de avaliação e recomendação.*

### Fase 5 — Operação e governança

Integração ao fluxo de trabalho da equipe, capacitação, definição do canal de
contestação e instalação do comitê de acompanhamento previsto nas
[salvaguardas](salvaguardas.html).

---

## O que a Prefeitura precisa prover

| Item | Descrição |
|---|---|
| **Instrumento jurídico** | Convênio ou termo de cooperação com a UFT |
| **Extração de dados** | Conforme a lista acima, em ambiente controlado |
| **Interlocução técnica** | Um servidor da Sefin que conheça o cadastro e o fluxo de cobrança |
| **Validação de negócio** | Confirmação de que a ordenação faz sentido operacional |
| **Participação da Procuradoria** | Especialmente quanto ao uso na execução fiscal |

Não há necessidade de aquisição de software ou infraestrutura: o sistema roda em
ferramentas abertas e sem custo de licenciamento.

---

## O que a UFT oferece

- O sistema já construído e documentado
- Recalibração e auditoria com os dados reais
- Acompanhamento técnico durante o piloto
- Documentação de transparência em formato aberto, apta a exame por órgãos de controle
- Formação de estudantes envolvidos com um problema público concreto do município

---

## Retorno esperado do piloto

Não é possível — nem seria honesto — prometer um valor de recuperação antes de
ver os dados reais. O que a prova de conceito indica é o **mecanismo**: o
retorno se concentra fortemente em uma parcela da carteira, e ordenar por
retorno esperado captura essa concentração.

A pergunta "quanto o município vai recuperar a mais" tem uma única resposta
tecnicamente defensável: **é o que o piloto com grupo de comparação vai medir**.

---

## Contato

**Prof. Dr. David Nadler Prata**
Coordenação do Eixo II — Bacharelado Interdisciplinar em Inteligência Artificial
Universidade Federal do Tocantins

Uma apresentação ao vivo do painel, com a equipe da Sefin, pode ser agendada a
qualquer momento.
