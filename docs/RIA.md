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
alta). Limite de disparidade: **0,10** de diferença, fixado antes da auditoria.

**De onde vem o limite.** O 0,10 é a convenção do AI Fairness 360 (Bellamy et
al., 2019), que considera justa uma diferença de paridade entre −0,1 e 0,1. A
referência jurídica mais antiga é a regra dos quatro quintos da EEOC (1978),
que olha a razão entre as taxas de seleção e pede ao menos 0,8 — e que Barocas,
Hardt e Narayanan (2023) tratam como referência, não como regra estrita.
Nenhum dos dois é norma brasileira, e não há limite consagrado entre eles; por
isso o laudo informa a diferença e a razão.

**Paridade Demográfica** — as taxas de seleção devem ser parecidas entre grupos:

$$\text{DPD} = \max_a P(\hat{Y}=1 \mid A=a) - \min_a P(\hat{Y}=1 \mid A=a)$$

**Igualdade de Oportunidade** — o recall deve ser parecido entre grupos:

$$\text{EOD} = \max_a P(\hat{Y}=1 \mid Y=1, A=a) - \min_a P(\hat{Y}=1 \mid Y=1, A=a)$$

### 2.2 Resultados

**Modelo 1 — inadimplência: REPROVADO nos dois testes**

| Grupo | n | Prevalência real | Taxa de seleção | Recall | FPR | Precisão |
|---|---|---|---|---|---|---|
| alta | 1.030 | 0,293 | 0,203 | 0,450 | 0,100 | 0,651 |
| média | 1.674 | 0,376 | 0,341 | 0,640 | 0,161 | 0,706 |
| baixa | 1.966 | 0,555 | 0,535 | 0,775 | 0,235 | 0,804 |

| Teste | Diferença | Razão | Resultado |
|---|---|---|---|
| Paridade Demográfica | 0,3322 | 0,379 | **reprovado** |
| Igualdade de Oportunidade | 0,3251 | 0,581 | **reprovado** |

**Modelo 2 — recuperabilidade: REPROVADO na paridade, APROVADO na igualdade de oportunidade**

| Grupo | n | Prevalência real | Taxa de seleção | Recall | FPR | Precisão |
|---|---|---|---|---|---|---|
| alta | 256 | 0,484 | 0,492 | 0,637 | 0,356 | 0,627 |
| média | 691 | 0,450 | 0,371 | 0,553 | 0,221 | 0,672 |
| baixa | 1.064 | 0,402 | 0,411 | 0,565 | 0,307 | 0,554 |

| Teste | Diferença | Razão | Resultado |
|---|---|---|---|
| Paridade Demográfica | 0,1217 | 0,753 | **reprovado** |
| Igualdade de Oportunidade | 0,0840 | 0,868 | aprovado |

**Incerteza da medida.** O conjunto de teste do Modelo 2 tem só 256 dívidas
de setores de renda alta, então a diferença medida oscila com a amostra. O
intervalo de confiança de 95%, por bootstrap dentro de cada grupo
(`src/fairness.py::intervalo_bootstrap`, 2.000 reamostras):

| Modelo e teste | Diferença | IC 95% | Reamostras acima de 0,10 |
|---|---|---|---|
| 1 — Paridade Demográfica | 0,3322 | 0,299 a 0,365 | 100% |
| 1 — Igualdade de Oportunidade | 0,3251 | 0,262 a 0,387 | 100% |
| 2 — Paridade Demográfica | 0,1217 | 0,054 a 0,190 | 73% |
| 2 — Igualdade de Oportunidade | 0,0840 | 0,019 a 0,190 | 47% |

O Modelo 1 reprova sem ambiguidade. No Modelo 2, os dois intervalos contêm
0,10: a amostra não permite afirmar de que lado do limite a disparidade real
está — a da paridade pode estar abaixo, a do recall pode estar acima. Isso **não muda o
resultado**: a aprovação é a estimativa pontual contra o limite fixado antes da
auditoria, e trocar o critério depois de ver o número seria escolher a régua
pelo resultado. O que o intervalo mostra é que a decisão de aplicar a
mitigação deve valer mesmo sob incerteza, e que a auditoria com mais dados é
prioridade. (O intervalo de uma diferença máxima entre três taxas tende a ficar
um pouco deslocado para cima, porque o ruído infla o máximo.)

### 2.3 Discussão honesta

**O viés do Modelo 1 é real e grave.** Um morador de setor de renda baixa tem
**2,6 vezes** mais chance de ser sinalizado como inadimplente que um morador de
setor de renda alta (0,535 contra 0,203). Se essa saída dirigisse a intensidade
de fiscalização, o sistema concentraria o aparato fiscal do município sobre a
população mais pobre — exatamente o risco que O'Neil (2021) descreve: um modelo
que aprende uma desigualdade existente e a devolve como decisão automatizada,
com aparência de neutralidade técnica.

**Mas o viés não é um bug de programação.** A prevalência real de inadimplência
difere de fato entre os grupos (0,555 contra 0,293). Um classificador bem
calibrado *tem* que refletir isso — é o que significa estar calibrado. O
problema não está no modelo: está em usar essa saída para decidir sobre pessoas.

**A impossibilidade matemática.** Quando a prevalência difere entre grupos,
paridade demográfica e calibração não podem valer ao mesmo tempo (Kleinberg,
Mullainathan e Raghavan, 2016). Não existe escolha tecnicamente neutra aqui:
há uma decisão de valor a tomar, e ela deve ser tomada explicitamente, por
quem tem legitimidade para isso — não escondida num hiperparâmetro.

**O Modelo 2 reprova na paridade e passa na igualdade de oportunidade.** Ele
considera recuperáveis 49,2% das dívidas dos setores de renda alta, 41,1% das
de renda baixa e 37,1% das de renda média. Não há um gradiente por renda — a
faixa menos selecionada é a média —, e a seleção maior na faixa alta acompanha
a recuperação real maior (0,484 contra 0,450 e 0,402). O recall fica entre
0,553 e 0,637, dentro do limite. O atributo dominante é o tempo de
inadimplência (0,175 na importância por permutação); valor venal (0,018) e
distância ao centro (0,006), que funcionam como substitutos da renda, pesam
pouco.

**O algoritmo também é uma decisão ética.** Com gradient boosting, o mesmo
Modelo 2 pesava valor venal e distância ao centro três a dez vezes mais,
reprovava também na igualdade de oportunidade (0,115) e reconhecia menos as
dívidas recuperáveis dos setores pobres. A troca para regressão logística,
motivada por desempenho, reduziu o uso dos substitutos da renda. Tirar a faixa
de renda dos atributos não bastou; foi preciso também um modelo que não a
reconstruísse por outros caminhos.

**O que "ser selecionado" significa muda o sentido do dano.** No Modelo 2, ser
selecionado é entrar no topo da fila. Se a ação for cobrança coercitiva, o
viés pesa sobre a faixa mais selecionada, a alta. Se for oferta de
parcelamento ou de regularização, quem perde são os devedores das faixas menos
selecionadas que pagariam e não são procurados. O mesmo número tem leituras opostas conforme a ação; por
isso a auditoria precisa ser lida junto com o uso que a Sefin fizer da fila.

### 2.4 Mitigação adotada

**Decisão 1 — restringir o uso do Modelo 1.** A priorização de cobrança usa
exclusivamente o Modelo 2. O Modelo 1 fica restrito a uso diagnóstico
(dimensionar o problema, planejar educação fiscal, subsidiar política pública).
É a mitigação mais eficaz porque elimina o dano na origem, em vez de tentar
corrigi-lo depois.

**Decisão 2 — corte calibrado por grupo no Modelo 2, obrigatório.** Sem ele, o
Modelo 2 reprova na paridade demográfica; por isso a mitigação deixa de ser
opcional.
Implementada em `src/fairness.py::simular_mitigacao`, seguindo o
pós-processamento de Hardt, Price e Srebro (2016):

| Grupo | Corte calibrado | Taxa de seleção antes | Depois | Recall depois |
|---|---|---|---|---|
| alta | 0,5383 | 0,492 | 0,406 | 0,532 |
| média | 0,4844 | 0,371 | 0,408 | 0,601 |
| baixa | 0,5021 | 0,411 | 0,407 | 0,561 |

Disparidade na taxa de seleção: **0,1217 → 0,0019**. A diferença de recall cai
de 0,084 para 0,069 e continua abaixo do limite de 0,10.

Escolhemos essa técnica por três razões: não exige retreinar, não altera os
dados, e — decisivo num órgão público — é **auditável**: o corte de cada grupo
é um número explícito, publicável e contestável. Uma mitigação que se esconde
dentro da função de perda não pode ser fiscalizada pela sociedade.

**Custo assumido, declarado abertamente.** Aplicar cortes diferentes por grupo
é tratar pessoas de forma diferente segundo o grupo — o que exige justificativa
pública explícita. A justificativa aqui é que a alternativa (corte único)
produz disparidade maior. Não é uma solução sem custo; é uma escolha entre dois
custos, feita às claras.

**Decisão 3 — exclusão dos grupos protegidos.** 1.320 beneficiários do IPTU
Social (6,6% da carteira) são removidos antes de qualquer treino ou predição.

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
| `tempo_inadimplencia_dias` | 0,1753 |
| `qtd_parcelamentos_anteriores` | 0,0182 |
| `valor_venal` | 0,0181 |
| `valor_divida_consolidada` | 0,0149 |
| `parcelamento_rompido` | 0,0147 |
| `valor_iptu_anual` | 0,0073 |
| `distancia_centro_km` | 0,0056 |
| `tipo_imovel` | 0,0036 |
| `setor_urbano` | 0,0010 |

Como o Modelo 2 é uma regressão logística, a explicação pode ir além da
importância: cada atributo tem um coeficiente, com sinal, que diz em que
direção ele empurra a probabilidade.

### 3.2 Exemplo de explicação gerada

Predição real do simulador do painel, para um imóvel residencial no Plano
Diretor Sul, valor venal R$ 180.000, dívida de R$ 4.800 com 540 dias de
inadimplência e um parcelamento anterior não rompido:

> **Probabilidade de recuperação: 65,0% — faixa média.**
> **Retorno esperado: R$ 3.118,52.**

Explicação em linguagem acessível ao contribuinte:

> Sua dívida foi classificada como de **média recuperabilidade**, perto do
> limite da faixa alta. O fator que mais pesou foi o **tempo de inadimplência**
> (540 dias): dívidas mais recentes são recuperadas com mais frequência, e a sua
> é mais recente que a maioria. O fato de você ter **aderido a um parcelamento
> anterior sem rompê-lo** também contribuiu positivamente. Essa classificação
> define apenas a **ordem de atendimento** da equipe de cobrança — ela não altera
> o valor devido, não gera novo encargo e não restringe nenhum direito seu. Você
> pode solicitar revisão desta classificação por decisão humana.

### 3.3 Avaliação crítica da compreensibilidade

A explicação acima é compreensível, mas **não é completa**, e é honesto dizer
isso. A importância por permutação é *global*: descreve o que o modelo considera
relevante em média, não a contribuição exata daquele caso. Um contribuinte que
pergunte "por que **eu** e não meu vizinho?" não é respondido por ela.

**Encaminhamento para produção:** como o Modelo 2 é uma regressão logística, a
resposta exata já existe — cada coeficiente multiplicado pelo valor do atributo
daquele contribuinte dá a contribuição dele para o resultado, e a soma das
contribuições é a própria predição. O PoC ainda não mostra essa decomposição.
O passo seguinte é exibi-la e submeter o texto gerado a teste de compreensão
com contribuintes reais — não apenas à avaliação da equipe técnica. Uma
explicação que só a equipe entende não cumpre o Art. 20.

---

## Seção 4 — Impactos sociais e recomendações

### 4.1 Impactos positivos esperados

- **Eficiência da máquina pública.** Nas dívidas do conjunto de teste,
  trabalhar os 20% primeiros da fila alcança **47,4%** do valor de fato
  recuperado, contra 20% de uma ordem aleatória. A regra simples "maiores
  dívidas primeiro" alcança 43,8%: o modelo acrescenta 3,7 pontos percentuais
  (IC 95% de 0,5 a 7,2). Quase todo o ganho vem de ordenar pelo valor — e é
  com essa regra simples, não com a ordem aleatória, que a Sefin deve comparar
  o sistema antes de adotá-lo.
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
| Concentrar fiscalização sobre população pobre | **Alta** | Modelo 1 fora da priorização; corte calibrado no Modelo 2 |
| Fila que prioriza uma faixa de renda mais que as outras | Média | Corte calibrado por grupo, obrigatório no Modelo 2 |
| Modelo que reconstrói a renda por atributos substitutos | Média | Algoritmo escolhido também pela auditoria; importância dos substitutos acompanhada a cada retreino |
| Automatizar decisão sem revisão humana | **Alta** | Sistema entrega fila, não veredito; registro obrigatório de predições |
| Atingir contribuinte vulnerável | **Alta** | Exclusão do IPTU Social por construção, verificada em teste |
| Reforçar viés histórico da cobrança | Média | Auditoria obrigatória a cada retreino, com publicação |
| Contribuinte não entender a classificação | Média | Explicação em linguagem acessível; canal de contestação |
| Falsa sensação de objetividade técnica | Média | Limitações declaradas no painel e nesta seção |
| Vazamento de dados fiscais | **Alta** (em produção) | Pseudonimização, controle de acesso, retenção limitada |
| Deixar dívidas prescreverem por estarem no fim da fila | **Alta** | Alerta de prescrição no painel e no assistente; controle de prazo fora da ordem por retorno esperado |

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
6. **Reavaliação anual** do proxy de renda e dos cortes das faixas.
7. **Não estender o sistema** a decisões sobre benefícios fiscais, certidões ou
   qualquer ato restritivo de direitos.
8. **Descontinuar** se a auditoria apontar disparidade crescente sem mitigação
   viável. Um sistema que não pode ser corrigido deve ser desligado.
9. **Controlar a prescrição fora da fila.** Priorizar não é dispensar: a fila
   define a ordem, e nenhuma dívida pode ser abandonada por ficar no fim dela.
   Dívidas próximas dos cinco anos (CTN, art. 174) precisam de um fluxo próprio,
   validado pela Procuradoria.
10. **Comparar com a regra simples antes de adotar.** Com dados reais, medir se
    a fila do modelo recupera mais que "maiores dívidas primeiro". Se a
    diferença for desprezível, a regra simples é mais fácil de explicar e de
    auditar.

### 4.4 Conclusão

O sistema é **viável e recomendável para uso assistido**, na configuração
descrita: priorização pelo Modelo 2, com corte calibrado por grupo, exclusão
do IPTU Social e revisão humana obrigatória.

O achado mais importante deste trabalho é metodológico, e vale além deste
projeto: **duas escolhas tomadas antes da auditoria mudaram o viés mais do que
qualquer ajuste depois dela**. A primeira é a pergunta. "Quem provavelmente
deve?" produz um modelo que aprende sobre pobreza (disparidade de 0,33, contra
os setores pobres). "De quem se consegue recuperar?" produz um modelo que
aprende sobretudo sobre o processo de cobrança — o tempo de inadimplência
domina. A segunda é o algoritmo. Com gradient boosting, o Modelo 2 reconstruía
a renda por substitutos e reprovava nos dois testes; com regressão logística,
esses substitutos perderam peso e ficou só a diferença de seleção (0,12), que
acompanha a recuperação real maior na faixa alta. Nenhuma das duas escolhas
elimina o viés: o que torna o Modelo 2 utilizável é a combinação delas com a
mitigação explícita — e nada disso dispensa a auditoria a cada retreino.

---

## Referências

- BAROCAS, S.; HARDT, M.; NARAYANAN, A. *Fairness and Machine Learning*, 2023.
- BELLAMY, R. K. E. et al. *AI Fairness 360: An Extensible Toolkit for
  Detecting and Mitigating Algorithmic Bias*. IBM Journal of Research and
  Development, v. 63, n. 4/5, 2019.
- EEOC. *Uniform Guidelines on Employee Selection Procedures*, 29 CFR 1607,
  1978 (regra dos quatro quintos).
- HARDT, M.; PRICE, E.; SREBRO, N. *Equality of Opportunity in Supervised
  Learning*. NeurIPS, 2016.
- KLEINBERG, J.; MULLAINATHAN, S.; RAGHAVAN, M. *Inherent Trade-Offs in the Fair
  Determination of Risk Scores*. 2016.
- MITCHELL, M. et al. *Model Cards for Model Reporting*. ACM FAccT, 2019.
- O'NEIL, C. *Algoritmos de Destruição em Massa*. São Paulo, 2021.
- BRASIL. Lei n. 13.709/2018 (LGPD); Lei n. 5.172/1966 (CTN).
