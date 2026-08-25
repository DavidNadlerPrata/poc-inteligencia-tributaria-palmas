# Salvaguardas e conformidade

<p class="subtitulo">O que foi feito para que o sistema não produza efeito indesejado sobre contribuintes — e como isso é verificado.</p>

---

## Por que esta seção existe

Aplicar inteligência artificial à cobrança tributária é diferente de aplicá-la a
uma previsão de demanda. Há pessoas do outro lado, o Estado tem poder sobre
elas, e um erro sistemático não afeta um cliente: afeta um cidadão que não
escolheu participar.

Por isso a prova de conceito tratou as salvaguardas como parte do produto, e não
como documentação posterior.

---

## 1. Beneficiários do IPTU Social ficam fora

Idosos, aposentados, pensionistas e pessoas com deficiência de baixa renda são
isentos pelo IPTU Social. Esses contribuintes são **removidos da base antes de
qualquer processamento** — não aparecem na fila, não recebem estimativa, não são
alvo do sistema em nenhuma etapa.

Essa exclusão não depende da atenção de quem opera o sistema. Ela é verificada
automaticamente a cada alteração: se alguém modificar o sistema de forma que um
beneficiário volte a aparecer na fila, a verificação falha e a alteração é
bloqueada antes de entrar em operação.

<div class="destaque">
<p>Regras éticas que dependem de disciplina humana são cumpridas até o dia em que
alguém tem pressa. Por isso esta foi convertida em verificação automática.</p>
</div>

---

## 2. O sistema foi auditado quanto ao tratamento entre regiões

A preocupação legítima é: **o sistema vai concentrar a fiscalização sobre os
bairros mais pobres?**

Para responder, o comportamento do sistema foi medido separadamente em setores
de renda alta, média e baixa, com dois critérios técnicos reconhecidos
internacionalmente. Os dois comparam se o sistema trata as regiões de forma
equilibrada — o primeiro quanto à frequência com que seleciona casos, o segundo
quanto à qualidade do acerto.

| Critério | Diferença encontrada | Limiar aceitável | Situação |
|---|---|---|---|
| Equilíbrio na seleção de casos | 0,047 | 0,10 | <span class="selo selo-aprovado">aprovado</span> |
| Equilíbrio na qualidade do acerto | 0,041 | 0,10 | <span class="selo selo-aprovado">aprovado</span> |

Os valores ficaram bem abaixo do limiar — cerca de um quarto do máximo tolerado.
Na prática, isso significa que um débito de perfil semelhante recebe tratamento
semelhante, independentemente da região da cidade em que está.

### Um achado que vale registrar

Durante o desenvolvimento, foram testadas **duas formas de fazer a pergunta ao
sistema**:

- *"Quem provavelmente vai deixar de pagar?"*
- *"De quem se consegue recuperar o que já está inscrito?"*

A primeira pergunta produziu um sistema **fortemente desequilibrado**: ele
sinalizava moradores de setores de renda baixa com frequência muito maior. A
razão é simples e não é culpa do método — a inadimplência é de fato mais
frequente onde a renda é menor, e qualquer sistema honesto reflete isso. O
problema não está no cálculo: está em usar esse resultado para direcionar
fiscalização.

A segunda pergunta produziu um sistema equilibrado, porque a chance de recuperar
uma dívida depende muito mais do tempo de inscrição e do histórico de
parcelamento do que da renda da região.

**A decisão de projeto foi adotar apenas a segunda.** O sistema em operação
responde a "de quem se recupera", nunca a "quem vai dever". A primeira análise
tem valor para planejamento de política pública — dimensionar o problema,
orientar campanhas de educação fiscal — mas não para direcionar cobrança.

---

## 3. Proteção de dados (LGPD)

### Nesta prova de conceito

**Nenhum dado pessoal foi utilizado.** Os dados públicos de arrecadação
agregada, obtidos do portal de transparência do próprio município, não
identificam contribuintes. A carteira individual usada nos testes é simulada.

### Em operação real

| Aspecto | Tratamento previsto |
|---|---|
| **Base legal** | Art. 7º, II e III, e Art. 23 da LGPD — execução de política pública e cumprimento de obrigação legal pelo ente público. Não é hipótese de consentimento: o contribuinte não escolhe ser cobrado |
| **Minimização** | Nome, CPF e endereço não entram no processamento analítico |
| **Pseudonimização** | A inscrição imobiliária é substituída por código irreversível |
| **Retenção** | Limitada ao prazo de prescrição do crédito tributário |
| **Registro** | Toda estimativa que motive ação de cobrança fica registrada, viabilizando contestação |
| **Avaliação prévia** | Relatório de impacto à proteção de dados junto ao encarregado (DPO) do município antes da entrada em operação |

---

## 4. Direito à explicação

O Art. 20 da LGPD assegura ao cidadão o direito de entender decisões automatizadas
que o afetem e de solicitar revisão. O sistema foi construído para atender isso:
para cada estimativa, é possível apresentar os fatores que a determinaram, em
linguagem compreensível.

Exemplo de explicação gerada para um caso real da demonstração:

<blockquote>
<p>Sua dívida foi classificada como de <strong>alta recuperabilidade</strong>. O fator que
mais pesou foi o <strong>tempo de inadimplência</strong> (540 dias): dívidas mais recentes
são recuperadas com mais frequência. O fato de você ter <strong>aderido a um
parcelamento anterior sem rompê-lo</strong> também contribuiu positivamente.</p>

<p>Essa classificação define apenas a <strong>ordem de atendimento</strong> da equipe de
cobrança — ela não altera o valor devido, não gera novo encargo e não restringe
nenhum direito seu. Você pode solicitar revisão desta classificação por decisão
humana.</p>
</blockquote>

---

## 5. Limites que devem ser respeitados

A prova de conceito documenta usos que **não** são recomendados, e que
comprometeriam a legitimidade do sistema:

- Automatizar qualquer ato de cobrança, protesto ou execução fiscal
- Negar parcelamento, benefício fiscal ou certidão com base na estimativa
- Definir intensidade de fiscalização sobre pessoa física identificada
- Estender o sistema a decisões restritivas de direitos
- Aplicar em outro município sem novo treinamento e nova auditoria

---

## 6. Recomendações de governança

Para uso responsável em operação, recomenda-se:

1. **Revisão humana obrigatória** antes de qualquer ato de cobrança
2. **Auditoria semestral** com os mesmos critérios, publicada integralmente —
   inclusive quando o resultado for desfavorável
3. **Canal de contestação divulgado no próprio documento de cobrança**, com
   prazo de resposta definido
4. **Comitê de acompanhamento** com participação da Procuradoria, do encarregado
   de dados e de representação da sociedade civil
5. **Descontinuidade** caso a auditoria aponte desequilíbrio crescente sem
   mitigação viável — um sistema que não pode ser corrigido deve ser desligado

---

## Transparência como método

A documentação técnica completa do sistema — incluindo o desempenho medido, os
vieses encontrados e as limitações conhecidas — foi produzida em formato aberto
e está disponível para exame por qualquer parte interessada, incluindo órgãos de
controle.

Isso é deliberado. Um sistema de decisão pública cuja lógica não pode ser
examinada não deveria ser adotado, por melhor que seja seu desempenho.
