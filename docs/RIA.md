# Relatório de Impacto Algorítmico (RIA)

Sistema de Inteligência Tributária de Palmas-TO — **Componente C** do portfólio
do Projeto Integrador, Eixo II.

| | |
|---|---|
| **Sistema** | Predição de inadimplência e priorização da dívida ativa |
| **Versão** | 0.1.0 (prova de conceito acadêmica) |
| **Responsável** | Equipe do Projeto Integrador — Eixo II / UFT |
| **Coordenação** | Prof. Dr. David Nadler Prata |

---

## Seção 1 — Mapeamento de dados pessoais e sensíveis

### 1.1 O que este PoC efetivamente trata

A distinção mais importante deste relatório: **o PoC não trata dados pessoais
reais**. O registro individual de dívida ativa é dado pessoal, protegido, e não
está disponível publicamente. O que o sistema coleta de verdade são agregados
de arrecadação, que não identificam ninguém.

| Dado | Origem | Categoria (LGPD) | Situação neste PoC |
|---|---|---|---|
| Arrecadação por código/órgão/mês | API pública da Prefeitura | Não pessoal (agregado) | **Real, coletado** |
| Inscrição imobiliária | — | Pessoal (identifica o titular) | **Sintético e pseudonimizado** |
| Valor venal, área, tipo do imóvel | — | Pessoal (vinculado ao titular) | **Sintético** |
| Histórico de inadimplência | — | Pessoal | **Sintético** |
| Faixa de renda do setor | Proxy IBGE | Não pessoal (agregado territorial) | **Sintético** |
| Condição de IPTU Social | — | **Sensível** — revela idade, deficiência ou condição previdenciária | **Sintético; usado apenas para excluir** |
| CPF/CNPJ, nome, endereço | — | Pessoal / identificador direto | **Não coletado, não usado** |

### 1.2 Se o sistema for para produção

Esta seção existe porque o caminho da produção precisa estar mapeado antes de
ser percorrido, não depois.

**Base legal.** Art. 7º, II e III, e Art. 23 da LGPD: tratamento por pessoa
jurídica de direito público para execução de política pública e cumprimento de
obrigação legal — no caso, a cobrança do crédito tributário municipal (CTN,
Art. 201). **Não é hipótese de consentimento:** o contribuinte não escolhe ser
cobrado, e pedir consentimento aqui seria juridicamente incorreto e eticamente
enganoso.

**Dado sensível exige cuidado redobrado.** A condição de beneficiário do IPTU
Social revela idade avançada, deficiência ou condição previdenciária —
categorias do Art. 5º, II da LGPD. Neste sistema esse dado tem **uma única
função: excluir a pessoa do universo de cobrança**. Ele nunca entra como
atributo preditivo. Essa é uma decisão de projeto que deve ser preservada em
qualquer evolução do sistema, e verificada por teste automatizado.

**Medidas técnicas exigidas em produção:**

| Medida | Detalhe |
|---|---|
| Pseudonimização | Inscrição imobiliária substituída por hash SHA-256 com sal em cofre de segredos — nunca no código |
| Minimização | Nome, CPF e endereço não entram no pipeline analítico |
| Retenção | Dados de treino por 5 anos (prescrição do crédito tributário, CTN Art. 174); logs de predição por 5 anos, para viabilizar contestação |
| Controle de acesso | Perfil por função; a fila de cobrança não é acessível fora da equipe designada |
| Registro de operações | Toda predição que motive ação de cobrança é logada com score, versão do modelo e data |
| DPIA formal | Relatório de impacto à proteção de dados junto ao encarregado (DPO) do município, antes da entrada em operação |

---

## Seção 2 — Análise de justiça algorítmica

### 2.1 Métricas aplicadas

Grupo protegido: **faixa de renda predominante do setor urbano** (baixa, média,
alta). Limiar de alerta: **0,10**.

**Paridade Demográfica** — as taxas de seleção devem ser parecidas entre grupos:

$$\text{DPD} = \max_a P(\hat{Y}=1 \mid A=a) - \min_a P(\hat{Y}=1 \mid A=a)$$

**Igualdade de Oportunidade** — o recall deve ser parecido entre grupos:

$$\text{EOD} = \max_a P(\hat{Y}=1 \mid Y=1, A=a) - \min_a P(\hat{Y}=1 \mid Y=1, A=a)$$

### 2.2 Resultados

**Modelo 1 — inadimplência: REPROVADO nos dois testes**

| Grupo | n | Prevalência real | Taxa de seleção | Recall | FPR | Precisão |
|---|---|---|---|---|---|---|
| alta | 1.028 | 0,367 | 0,203 | 0,310 | 0,141 | 0,560 |
| média | 1.647 | 0,477 | 0,427 | 0,559 | 0,307 | 0,625 |
| baixa | 1.977 | 0,605 | 0,678 | 0,786 | 0,512 | 0,702 |

| Teste | Diferença | Razão | Resultado |
|---|---|---|---|
| Paridade Demográfica | 0,4745 | 0,300 | **reprovado** |
| Igualdade de Oportunidade | 0,4757 | 0,395 | **reprovado** |

**Modelo 2 — recuperabilidade: APROVADO nos dois testes**

| Grupo | n | Prevalência real | Taxa de seleção | Recall | FPR | Precisão |
|---|---|---|---|---|---|---|
| alta | 704 | 0,548 | 0,619 | 0,723 | 0,494 | 0,640 |
| média | 1.362 | 0,499 | 0,583 | 0,706 | 0,460 | 0,605 |
| baixa | 1.775 | 0,515 | 0,572 | 0,682 | 0,455 | 0,614 |

| Teste | Diferença | Razão | Resultado |
|---|---|---|---|
| Paridade Demográfica | 0,0475 | 0,923 | aprovado |
| Igualdade de Oportunidade | 0,0412 | 0,943 | aprovado |

### 2.3 Discussão honesta

**O viés do Modelo 1 é real e grave.** Um morador de setor de renda baixa tem
**3,3 vezes** mais chance de ser sinalizado como inadimplente que um morador de
setor de renda alta (0,678 contra 0,203). Se essa saída dirigisse a intensidade
de fiscalização, o sistema concentraria o aparato fiscal do município sobre a
população mais pobre — exatamente o risco que O'Neil (2021) descreve: um modelo
que aprende uma desigualdade existente e a devolve como decisão automatizada,
com aparência de neutralidade técnica.

**Mas o viés não é um bug de programação.** A prevalência real de inadimplência
difere de fato entre os grupos (0,605 contra 0,367). Um classificador bem
calibrado *tem* que refletir isso — é o que significa estar calibrado. O
problema não está no modelo: está em usar essa saída para decidir sobre pessoas.

**A impossibilidade matemática.** Quando a prevalência difere entre grupos,
paridade demográfica e calibração não podem valer ao mesmo tempo (Kleinberg,
Mullainathan e Raghavan, 2016). Não existe escolha tecnicamente neutra aqui:
há uma decisão de valor a tomar, e ela deve ser tomada explicitamente, por
quem tem legitimidade para isso — não escondida num hiperparâmetro.

**Por que o Modelo 2 passa.** A recuperabilidade tem prevalência parecida em
todos os grupos (0,50 a 0,55): recuperar uma dívida depende muito mais do tempo
desde a inscrição e do histórico de parcelamento do que da renda do setor. A
importância por permutação confirma — `tempo_inadimplencia_dias` domina (0,157),
mais de cinco vezes o segundo colocado, enquanto `setor_urbano` fica em 0,008.
**O modelo aprendeu a olhar para o processo, não para a pessoa.** É por isso que
ele pode ordenar a fila.

### 2.4 Mitigação adotada

**Decisão 1 — restringir o uso do Modelo 1.** A priorização de cobrança usa
exclusivamente o Modelo 2. O Modelo 1 fica restrito a uso diagnóstico
(dimensionar o problema, planejar educação fiscal, subsidiar política pública).
É a mitigação mais eficaz porque elimina o dano na origem, em vez de tentar
corrigi-lo depois.

**Decisão 2 — limiar calibrado por grupo no Modelo 2.** Implementada em
`src/fairness.py::simular_mitigacao`, seguindo o pós-processamento de Hardt,
Price e Srebro (2016):

| Grupo | Limiar calibrado | Taxa de seleção antes | Depois | Recall depois |
|---|---|---|---|---|
| alta | 0,5179 | 0,619 | 0,584 | 0,700 |
| média | 0,4990 | 0,583 | 0,584 | 0,709 |
| baixa | 0,4938 | 0,572 | 0,584 | 0,698 |

Disparidade na taxa de seleção: **0,0475 → 0,0006**.

Escolhemos essa técnica por três razões: não exige retreinar, não altera os
dados, e — decisivo num órgão público — é **auditável**: o limiar de cada grupo
é um número explícito, publicável e contestável. Uma mitigação que se esconde
dentro da função de perda não pode ser fiscalizada pela sociedade.

**Custo assumido, declarado abertamente.** Aplicar limiares diferentes por grupo
é tratar pessoas de forma diferente segundo o grupo — o que exige justificativa
pública explícita. A justificativa aqui é que a alternativa (limiar único)
produz disparidade maior. Não é uma solução sem custo; é uma escolha entre dois
custos, feita às claras.

**Decisão 3 — exclusão dos grupos protegidos.** 1.393 beneficiários do IPTU
Social (7,0% da carteira) são removidos antes de qualquer treino ou predição.

---

## Seção 3 — Direito à explicação e transparência

### 3.1 Técnica adotada

**Importância por permutação**, medida sobre o conjunto de teste: cada atributo
é embaralhado e mede-se quanto o ROC-AUC cai. Foi escolhida sobre SHAP e LIME
por três motivos: não depende do tipo de modelo, produz um número diretamente
interpretável ("o modelo perde tanto sem esta informação") e não introduz
dependência externa que dificulte a auditoria.

| Atributo | Importância |
|---|---|
| `tempo_inadimplencia_dias` | 0,1569 |
| `qtd_parcelamentos_anteriores` | 0,0295 |
| `valor_divida_consolidada` | 0,0281 |
| `parcelamento_rompido` | 0,0229 |
| `distancia_centro_km` | 0,0140 |
| `valor_venal` | 0,0116 |
| `area_construida_m2` | 0,0101 |
| `setor_urbano` | 0,0077 |

### 3.2 Exemplo de explicação gerada

Predição real do simulador do painel, para um imóvel residencial no Plano
Diretor Sul, valor venal R$ 180.000, dívida de R$ 4.800 com 540 dias de
inadimplência e um parcelamento anterior não rompido:

> **Probabilidade de recuperação: 74,1% — faixa alta.**
> **Retorno esperado: R$ 3.559,17.**

Explicação em linguagem acessível ao contribuinte:

> Sua dívida foi classificada como de **alta recuperabilidade**. O fator que mais
> pesou foi o **tempo de inadimplência** (540 dias): dívidas mais recentes são
> recuperadas com mais frequência. O fato de você ter **aderido a um parcelamento
> anterior sem rompê-lo** também contribuiu positivamente. Essa classificação
> define apenas a **ordem de atendimento** da equipe de cobrança — ela não altera
> o valor devido, não gera novo encargo e não restringe nenhum direito seu. Você
> pode solicitar revisão desta classificação por decisão humana.

### 3.3 Avaliação crítica da compreensibilidade

A explicação acima é compreensível, mas **não é completa**, e é honesto dizer
isso. A importância por permutação é *global*: descreve o que o modelo considera
relevante em média, não a contribuição exata daquele caso. Um contribuinte que
pergunte "por que **eu** e não meu vizinho?" não é respondido por ela.

**Encaminhamento para produção:** adotar SHAP com valores locais por predição,
que responde exatamente essa pergunta, e submeter o texto gerado a teste de
compreensão com contribuintes reais — não apenas à avaliação da equipe técnica.
Uma explicação que só a equipe entende não cumpre o Art. 20.

---

## Seção 4 — Impactos sociais e recomendações

### 4.1 Impactos positivos esperados

- **Eficiência da máquina pública.** Os 20% melhores casos da fila concentram
  **50,5%** do retorno esperado. Direcionar esforço por essa ordenação aumenta a
  recuperação sem ampliar a equipe.
- **Recursos para política pública.** Dívida ativa recuperada financia saúde,
  educação e infraestrutura. Não cobrar quem pode pagar transfere o custo para
  quem já paga.
- **Redução de arbitrariedade.** Um critério explícito e auditável é preferível
  a decisões pontuais não documentadas — desde que o critério seja publicado.
- **Transparência verificável.** Model Card e RIA públicos permitem escrutínio
  externo, algo raro na administração tributária.

### 4.2 Impactos negativos e riscos

| Risco | Gravidade | Mitigação adotada |
|---|---|---|
| Concentrar fiscalização sobre população pobre | **Alta** | Modelo 1 fora da priorização; limiar calibrado no Modelo 2 |
| Automatizar decisão sem revisão humana | **Alta** | Sistema entrega fila, não veredito; registro obrigatório de predições |
| Atingir contribuinte vulnerável | **Alta** | Exclusão do IPTU Social por construção, verificada em teste |
| Reforçar viés histórico da cobrança | Média | Auditoria obrigatória a cada retreino, com publicação |
| Contribuinte não entender a classificação | Média | Explicação em linguagem acessível; canal de contestação |
| Falsa sensação de objetividade técnica | Média | Limitações declaradas no painel e nesta seção |
| Vazamento de dados fiscais | **Alta** (em produção) | Pseudonimização, controle de acesso, retenção limitada |

### 4.3 Recomendações de uso responsável

1. **Publicar o Model Card e este RIA** junto com o sistema. Transparência que
   depende de pedido de acesso à informação não é transparência.
2. **Revisão humana obrigatória** antes de qualquer ato de cobrança.
3. **Auditoria semestral** com os dois testes, publicada integralmente,
   inclusive quando o resultado for desfavorável.
4. **Canal de contestação divulgado no próprio documento de cobrança**, com
   prazo de resposta definido.
5. **Comitê de acompanhamento** com participação da Procuradoria, do encarregado
   de dados (DPO) e de representação da sociedade civil.
6. **Reavaliação anual** do proxy de renda e dos limiares de faixa.
7. **Não estender o sistema** a decisões sobre benefícios fiscais, certidões ou
   qualquer ato restritivo de direitos.
8. **Descontinuar** se a auditoria apontar disparidade crescente sem mitigação
   viável. Um sistema que não pode ser corrigido deve ser desligado.

### 4.4 Conclusão

O sistema é **viável e recomendável para uso assistido**, na configuração
descrita: priorização pelo Modelo 2, com limiar calibrado por grupo, exclusão
do IPTU Social e revisão humana obrigatória.

O achado mais importante deste trabalho é metodológico, e vale além deste
projeto: **dois modelos treinados sobre os mesmos dados, com o mesmo algoritmo,
tiveram comportamentos éticos opostos** — reprovado nos dois testes contra
aprovado nos dois. A diferença não está na técnica, está na **pergunta**.
Perguntar "quem provavelmente deve?" produz um modelo que aprende sobre
pobreza. Perguntar "de quem se consegue recuperar?" produz um modelo que aprende
sobre processo de cobrança. A escolha da variável-alvo é uma decisão ética, não
apenas técnica — e é tomada antes de qualquer linha de código de modelagem.

---

## Referências

- BAROCAS, S.; HARDT, M.; NARAYANAN, A. *Fairness and Machine Learning*, 2023.
- HARDT, M.; PRICE, E.; SREBRO, N. *Equality of Opportunity in Supervised
  Learning*. NeurIPS, 2016.
- KLEINBERG, J.; MULLAINATHAN, S.; RAGHAVAN, M. *Inherent Trade-Offs in the Fair
  Determination of Risk Scores*. 2016.
- MITCHELL, M. et al. *Model Cards for Model Reporting*. ACM FAccT, 2019.
- O'NEIL, C. *Algoritmos de Destruição em Massa*. São Paulo, 2021.
- BRASIL. Lei n. 13.709/2018 (LGPD); Lei n. 5.172/1966 (CTN).
