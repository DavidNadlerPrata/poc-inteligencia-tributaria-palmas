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
alta). Limiar de alerta: **0,10** de diferença, fixado antes da auditoria.

**De onde vem o limiar.** O 0,10 é a convenção do AI Fairness 360 (Bellamy et
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

**Modelo 2 — recuperabilidade: REPROVADO nos dois testes, com viés no sentido oposto**

| Grupo | n | Prevalência real | Taxa de seleção | Recall | FPR | Precisão |
|---|---|---|---|---|---|---|
| alta | 256 | 0,484 | 0,500 | 0,629 | 0,379 | 0,609 |
| média | 691 | 0,450 | 0,386 | 0,540 | 0,261 | 0,629 |
| baixa | 1.064 | 0,402 | 0,380 | 0,514 | 0,289 | 0,545 |

| Teste | Diferença | Razão | Resultado |
|---|---|---|---|
| Paridade Demográfica | 0,1203 | 0,759 | **reprovado** |
| Igualdade de Oportunidade | 0,1150 | 0,817 | **reprovado** |

**Incerteza da medida.** O conjunto de teste do Modelo 2 tem só 256 dívidas
de setores de renda alta, então a diferença medida oscila com a amostra. O
intervalo de confiança de 95%, por bootstrap dentro de cada grupo
(`src/fairness.py::intervalo_bootstrap`, 2.000 reamostras):

| Modelo e teste | Diferença | IC 95% | Reamostras acima de 0,10 |
|---|---|---|---|
| 1 — Paridade Demográfica | 0,3322 | 0,299 a 0,365 | 100% |
| 1 — Igualdade de Oportunidade | 0,3251 | 0,262 a 0,387 | 100% |
| 2 — Paridade Demográfica | 0,1203 | 0,059 a 0,194 | 79% |
| 2 — Igualdade de Oportunidade | 0,1150 | 0,036 a 0,215 | 68% |

O Modelo 1 reprova sem ambiguidade. No Modelo 2, o intervalo contém 0,10: a
amostra não permite afirmar que a disparidade real passa do limiar — nem que
fica abaixo dele, já que o intervalo chega a 0,19. Isso **não muda o
resultado**: a aprovação é a estimativa pontual contra o limiar fixado antes da
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

**O Modelo 2 erra menos, mas também reprova — e no sentido oposto.** Ele
considera recuperáveis 50,0% das dívidas dos setores de renda alta e 38,0% das
dos setores de renda baixa, e reconhece menos as dívidas que de fato seriam
recuperadas nos setores pobres (recall de 0,514 contra 0,629). Há duas causas.
A primeira é real: a recuperação difere entre grupos (0,484 contra 0,402). A
segunda é aprendida: o atributo dominante é o tempo de inadimplência (0,218 na
importância por permutação), mas logo depois vêm valor venal (0,065) e
distância ao centro (0,055), que funcionam como substitutos da renda. Tirar a
faixa de renda dos atributos não bastou — os substitutos a trouxeram de volta.

**O que "ser selecionado" significa muda o sentido do dano.** No Modelo 2, ser
selecionado é entrar no topo da fila. Se a ação for cobrança coercitiva, o
viés pesa sobre os setores ricos. Se for oferta de parcelamento ou de
regularização, quem perde são os devedores dos setores pobres que pagariam e
não são procurados. O mesmo número tem leituras opostas conforme a ação; por
isso a auditoria precisa ser lida junto com o uso que a Sefin fizer da fila.

### 2.4 Mitigação adotada

**Decisão 1 — restringir o uso do Modelo 1.** A priorização de cobrança usa
exclusivamente o Modelo 2. O Modelo 1 fica restrito a uso diagnóstico
(dimensionar o problema, planejar educação fiscal, subsidiar política pública).
É a mitigação mais eficaz porque elimina o dano na origem, em vez de tentar
corrigi-lo depois.

**Decisão 2 — limiar calibrado por grupo no Modelo 2, obrigatório.** Sem ele, o
Modelo 2 reprova na auditoria; por isso a mitigação deixa de ser opcional.
Implementada em `src/fairness.py::simular_mitigacao`, seguindo o
pós-processamento de Hardt, Price e Srebro (2016):

| Grupo | Limiar calibrado | Taxa de seleção antes | Depois | Recall depois |
|---|---|---|---|---|
| alta | 0,5815 | 0,500 | 0,398 | 0,468 |
| média | 0,4957 | 0,386 | 0,398 | 0,553 |
| baixa | 0,4919 | 0,380 | 0,398 | 0,526 |

Disparidade na taxa de seleção: **0,1203 → 0,0008**. A diferença de recall cai
de 0,1150 para 0,085 e também fica abaixo do limiar de 0,10.

Escolhemos essa técnica por três razões: não exige retreinar, não altera os
dados, e — decisivo num órgão público — é **auditável**: o limiar de cada grupo
é um número explícito, publicável e contestável. Uma mitigação que se esconde
dentro da função de perda não pode ser fiscalizada pela sociedade.

**Custo assumido, declarado abertamente.** Aplicar limiares diferentes por grupo
é tratar pessoas de forma diferente segundo o grupo — o que exige justificativa
pública explícita. A justificativa aqui é que a alternativa (limiar único)
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
| `tempo_inadimplencia_dias` | 0,2184 |
| `valor_venal` | 0,0646 |
| `valor_divida_consolidada` | 0,0632 |
| `distancia_centro_km` | 0,0553 |
| `valor_iptu_anual` | 0,0527 |
| `area_construida_m2` | 0,0515 |
| `qtd_parcelamentos_anteriores` | 0,0364 |
| `parcelamento_rompido` | 0,0251 |
| `setor_urbano` | 0,0152 |

### 3.2 Exemplo de explicação gerada

Predição real do simulador do painel, para um imóvel residencial no Plano
Diretor Sul, valor venal R$ 180.000, dívida de R$ 4.800 com 540 dias de
inadimplência e um parcelamento anterior não rompido:

> **Probabilidade de recuperação: 69,9% — faixa alta.**
> **Retorno esperado: R$ 3.353,11.**

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
  **54,9%** do retorno esperado. Direcionar esforço por essa ordenação aumenta a
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
| Fila que reconhece menos as dívidas recuperáveis dos setores pobres | Média | Limiar calibrado por grupo, obrigatório no Modelo 2 |
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
tiveram vieses de intensidade e sentido diferentes**. Perguntar "quem
provavelmente deve?" produz um modelo que aprende sobre pobreza (disparidade de
0,33, contra os setores pobres). Perguntar "de quem se consegue recuperar?"
produz um modelo que aprende sobretudo sobre o processo de cobrança — o tempo
de inadimplência domina —, mas ainda carrega a renda pelos seus substitutos
(disparidade de 0,12, a favor dos setores ricos). A escolha da variável-alvo é
uma decisão ética, não apenas técnica, e reduz o viés; não o elimina. O que
torna o Modelo 2 utilizável é a combinação da pergunta certa com a mitigação
explícita — e nenhuma das duas dispensa a auditoria a cada retreino.

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
