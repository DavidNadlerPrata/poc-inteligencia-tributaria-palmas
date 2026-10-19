# Manual de coleta de dados da Prefeitura de Palmas

Guia prático para a **Sprint 2 — Coleta e ETL (Módulo 5)** do Projeto Integrador
do Eixo II.

Tudo aqui foi testado contra as APIs reais. Os comportamentos descritos —
inclusive as armadilhas — foram verificados em **19 de outubro de 2026**. Se algo
divergir quando você testar, a API mudou: registre o que encontrou, porque isso
é material de relatório.

---

## Sumário

1. [Panorama: existem duas APIs](#1-panorama-existem-duas-apis)
2. [Regras de conduta](#2-regras-de-conduta)
3. [Portal novo (NUCLEOGOV) — comece por aqui](#3-portal-novo-nucleogov--comece-por-aqui)
4. [API antiga — o histórico](#4-api-antiga--o-histórico)
5. [As cinco armadilhas](#5-as-cinco-armadilhas)
6. [Robustez: não perca duas horas de download](#6-robustez-não-perca-duas-horas-de-download)
7. [Descobrindo endpoints não documentados](#7-descobrindo-endpoints-não-documentados)
8. [Checklist antes de entregar](#8-checklist-antes-de-entregar)

---

## 1. Panorama: existem duas APIs

A Prefeitura de Palmas publica dados por **dois sistemas diferentes**, e essa é a
primeira coisa que confunde quem começa. Eles não são versões um do outro: têm
endereços, protocolos e conteúdos distintos.

| | Portal novo (NUCLEOGOV) | API antiga |
|---|---|---|
| **Endereço** | `acessoainformacao.palmas.to.gov.br/api` | `integracao.palmas.to.gov.br/apirest/` |
| **Protocolo** | HTTPS válido | HTTP (o HTTPS tem certificado quebrado) |
| **Método** | `POST` com formulário | `GET` com parâmetros na URL |
| **Período** | **Atualizado** (até o mês corrente) | **Congelado em junho de 2021** |
| **Conteúdo** | Receitas, despesas, servidores, contratos, licitações | Gastos diretos, arrecadação, folha |
| **Documentação** | Não há | `portaldatransparencia.palmas.to.gov.br/webservice/` |

**Qual usar?** Depende da pergunta:

- Precisa de dados **recentes**? Só o portal novo serve.
- Precisa de **série histórica longa** (2001–2021)? Só a API antiga tem.
- Quer **volume** para exercitar ETL? A API antiga tem 489 mil registros de folha
  de pagamento — o maior conjunto disponível.

> **Atenção ao combinar as duas.** Elas não compartilham identificadores nem
> esquema. Juntar as duas numa só tabela sem uma chave de ligação explícita
> produz um conjunto sem sentido — e é um erro comum.

---

## 2. Regras de conduta

Estas não são formalidades. A seção 11 do plano de ensino as exige, e um
trabalho que as ignore perde nota na dimensão de Rigor Ético.

1. **Pausa entre requisições.** Use ao menos 0,3 segundos. O servidor é público
   e compartilhado: um laço sem pausa é indistinguível de um ataque.
2. **Nunca rode coleta em automação recorrente.** Nada de agendar scripts ou
   colocar coleta em pipeline de integração contínua. Baixe uma vez, guarde o
   arquivo, trabalhe sobre ele.
3. **Registre a data da coleta** no README e no nome do arquivo. Os totais mudam
   (veja a seção 5.5) e um resultado sem data de coleta não é reproduzível.
4. **Verifique o `robots.txt`** do domínio antes de começar.
5. **Não tente obter dado pessoal.** A API não expõe quem deve quanto — e isso é
   proteção legal, não falha técnica. Não procure contornos.
6. **Use `timeout` em toda requisição.** Sem ele, seu script pode ficar
   pendurado indefinidamente numa conexão que o servidor abandonou.

---

## 3. Portal novo (NUCLEOGOV) — comece por aqui

### 3.1 Como a API funciona

Não é uma API REST convencional. É um único endereço que recebe `POST` com
formulário, e a operação desejada vai **dentro** de um campo JSON:

```
POST https://acessoainformacao.palmas.to.gov.br/api
Content-Type: application/x-www-form-urlencoded

multi_request=true
params={"k1": {"order": {}, "limit": "0, 1000", "acao": "sgreceitas/listar"}}
```

| Campo | O que é |
|---|---|
| `multi_request` | Sempre `true` |
| `params` | JSON com uma ou mais consultas; `k1` é o nome da primeira |
| `acao` | A operação (ver a tabela de módulos) |
| `limit` | `"offset, quantidade"` — é a paginação |
| `order` | Ordenação; `{}` aceita o padrão |

A resposta vem como `{"k1": {"total": N, "dados": [...]}}`.

### 3.2 Primeiro teste

Comece com **um registro só**. Se este bloco funcionar, metade do caminho está
feita:

```python
import json
import requests

BASE = "https://acessoainformacao.palmas.to.gov.br"

# ATENÇÃO: este User-Agent não é enfeite. Veja a armadilha 5.1.
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

sessao = requests.Session()

# 1) Visite a página do módulo para receber os cookies de sessão.
sessao.get(f"{BASE}/cidadao/transparencia/sgreceitas",
           headers={"User-Agent": NAVEGADOR}, timeout=60)

# 2) Agora chame a API.
consulta = {"k1": {"order": {}, "limit": "0, 1", "acao": "sgreceitas/listar"}}

resposta = sessao.post(
    f"{BASE}/api",
    data={"multi_request": "true", "params": json.dumps(consulta)},
    headers={
        "User-Agent": NAVEGADOR,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{BASE}/cidadao/transparencia/sgreceitas",
        "Origin": BASE,
    },
    timeout=60,
)

dados = resposta.json()["k1"]
print("total de registros:", dados["total"])
print("campos disponíveis:", list(dados["dados"][0].keys()))
```

Saída esperada (os números mudam com o tempo):

```
total de registros: 180976
campos disponíveis: ['total', 'orgao_nome', 'unidade_nome', 'codigo', 'orgao',
 'ano', 'mes', 'descricao', 'valor_orcado', 'valor_arrecado_mes',
 'valor_arrecado_periodo', 'covid', 'unidade_id', 'codigo_original']
```

### 3.3 Os módulos disponíveis

Totais medidos em **19/10/2026**:

| Módulo | Ação | Registros | Página de referência (para os cookies) |
|---|---|---|---|
| Receitas | `sgreceitas/listar` | 180.976 | `/cidadao/transparencia/sgreceitas` |
| Contratos | `sgcontratos/listar` | 8.897 | `/cidadao/transparencia/sgcontratos` |
| Despesas | `sgdespesas/listar` | 3.412 | `/cidadao/transparencia/sgdespesas` |
| Licitações | `sglicitacoes/listar` | 2.161 | `/cidadao/transparencia/sglicitacoes` |
| Servidores | `sgservidores/listar` | 16.116 | `/cidadao/transparencia/sgservidores` |

Os módulos `sg_estagiarios/listar` e `sgdispensas/listar` respondem, mas vêm
vazios — o portal não publica esses dados. **Retorno vazio não é erro de
código**; confirme com outra ação antes de depurar.

### 3.4 Paginação

A paginação é por deslocamento (`offset`), dentro do campo `limit`:

```python
def baixar_modulo(sessao, acao, referer, tamanho_pagina=1000, pausa=0.3):
    """Baixa um módulo inteiro, seguindo a paginação por offset."""
    import time

    registros = []
    offset = 0
    total = None

    while True:
        consulta = {"k1": {"order": {}, "limit": f"{offset}, {tamanho_pagina}",
                           "acao": acao}}
        resposta = sessao.post(
            f"{BASE}/api",
            data={"multi_request": "true", "params": json.dumps(consulta)},
            headers=cabecalhos(referer), timeout=90)
        resposta.raise_for_status()

        bloco = resposta.json()["k1"]
        pagina = bloco.get("dados") or []
        if not pagina:
            break

        if total is None:
            total = int(bloco["total"])
            print(f"total informado pela API: {total}")

        registros.extend(pagina)
        print(f"  {len(registros)}/{total}")

        offset += tamanho_pagina
        if offset >= total or len(pagina) < tamanho_pagina:
            break

        time.sleep(pausa)

    return registros
```

**Use `tamanho_pagina=1000`.** Testamos 5.000 e o servidor dá timeout; valores
entre 500 e 1000 funcionam bem. Com 1000, as 180 mil receitas levam cerca de
seis minutos.

### 3.5 Filtros

Receitas aceita `ano` e `mes` dentro da consulta:

```python
consulta = {"k1": {"order": {}, "limit": "0, 1000",
                   "acao": "sgreceitas/listar",
                   "ano": "2025", "mes": "7"}}
```

Isso reduz de 180 mil para cerca de 1.400 registros — comece sempre filtrando,
e só baixe a base inteira quando souber que precisa dela.

---

## 4. API antiga — o histórico

### 4.1 Como funciona

Esta é uma API REST convencional (Django REST Framework), com `GET` e paginação
por link:

```python
import requests
import urllib3

# Necessário: veja a armadilha 5.2.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "http://integracao.palmas.to.gov.br/apirest/gastos-diretos/"
resposta = requests.get(url, timeout=60, verify=False)
dados = resposta.json()

print("total:", dados["count"])          # 344323
print("próxima página:", dados["next"])  # URL pronta da página seguinte
print("registros nesta página:", len(dados["results"]))
```

A paginação é simples: siga o campo `next` até ele virar `None`.

```python
def baixar_tudo(url_inicial, params=None, pausa=0.3):
    """Segue o campo 'next' até o fim."""
    import time

    registros = []
    url = url_inicial
    primeira = True

    while url:
        # Os parâmetros valem só na primeira chamada: 'next' já vem completa.
        resposta = requests.get(url, params=params if primeira else None,
                                timeout=60, verify=False)
        resposta.raise_for_status()
        dados = resposta.json()

        registros.extend(dados.get("results", []))
        url = dados.get("next")
        primeira = False
        print(f"  {len(registros)}/{dados.get('count')}")

        time.sleep(pausa)

    return registros
```

### 4.2 Endpoints

Totais medidos em **19/10/2026** — idênticos aos de agosto, porque a base está
congelada:

| Endpoint | Registros | Por página | Conteúdo |
|---|---|---|---|
| `gastos-diretos/` | 344.323 | 100 | Empenhos, liquidações e pagamentos (2001–jun/2021) |
| `folha-pagamento/` | 489.378 | 400 | Um registro por servidor por mês |
| `arrecadacao/` | 3.542 | 100 | Receita agregada |

Baixar os três inteiros leva **bastante tempo**: gastos diretos são 3.444
páginas, e com a pausa obrigatória isso passa de 40 minutos. Não comece esse
download quinze minutos antes do prazo.

### 4.3 Filtros documentados

`gastos-diretos` aceita `inicio` e `fim` (formato `AAAA-MM-DD`), além de
`fornecedor`, `cpf_cnpj`, `unidade`, `natureza` e `empenho`.

```python
params = {"inicio": "2020-01-01", "fim": "2020-12-31"}
```

Os filtros de texto **diferenciam maiúsculas de minúsculas**. `"SECRETARIA"`
encontra; `"Secretaria"` não.

---

## 5. As cinco armadilhas

Cada uma destas custou tempo real de depuração. Lê-las agora economiza o seu.

### 5.1 O erro 403 que parece bloqueio de IP

**Sintoma:** o portal novo responde `403 Forbidden` para tudo, até para a página
inicial. Parece que seu IP foi bloqueado.

**Causa:** há um firewall de aplicação (WAF) que rejeita requisições cujo
`User-Agent` revele biblioteca de programação. O `requests` se identifica como
`python-requests/2.31` por padrão.

Verificado hoje:

| User-Agent enviado | Resposta |
|---|---|
| `python-requests/2.31` | **403 Forbidden** |
| `Mozilla/5.0 ... Chrome/126.0.0.0 ...` | **200 OK** |

**Solução:** envie um `User-Agent` de navegador em **todas** as requisições,
inclusive na que busca os cookies.

> **Isto é contorno legítimo?** Sim, e vale entender por quê. Os dados são
> públicos por lei, o acesso é o mesmo que um navegador faria, e a pausa entre
> requisições respeita o servidor. O WAF está barrando a *ferramenta*, não o
> *acesso*. O que não seria legítimo: burlar autenticação, resolver CAPTCHA ou
> ignorar `robots.txt`. Documente essa decisão no seu relatório — a discussão
> vale mais que a linha de código.

### 5.2 O certificado SSL quebrado

**Sintoma:** `SSLError: CERTIFICATE_VERIFY_FAILED` na API antiga, mesmo com a URL
em `http://`.

**Causa:** o servidor redireciona `http` para `https`, e o certificado tem a
cadeia incompleta. O problema é do servidor da Prefeitura, não do seu
computador — confirmei com `curl`, que reporta falha na verificação de revogação.

**Solução:**

```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

resposta = requests.get(url, verify=False, timeout=60)
```

> **Quando `verify=False` é aceitável?** Aqui sim: dado público, somente leitura,
> sem credencial nem envio de informação. **Nunca** faça isso em requisição com
> senha, token ou dado pessoal — desligar a verificação abre a porta para
> interceptação. Registre a justificativa em comentário no código, para que
> ninguém copie o padrão para onde ele é perigoso.

### 5.3 O filtro que mente — a mais perigosa

Esta armadilha é silenciosa, e por isso a pior: ela não dá erro, dá **resultado
errado**.

Medições de hoje no endpoint `gastos-diretos`:

| Consulta | `count` retornado | O que realmente aconteceu |
|---|---|---|
| sem filtro | 344.323 | baseline |
| `inicio=2024-01-01` | **0** | filtro válido, período sem dados |
| `ano=2024` | **0** | filtro válido, período sem dados |
| `ano_referencia=2024` | **344.323** | **filtro inexistente: foi IGNORADO** |
| `inicio=2021-01-01` | 3.945 | filtro válido, com dados |

Olhe a terceira linha. Pedimos dados de 2024 e recebemos **a base inteira**,
de 2001 a 2021, sem nenhum aviso. Um aluno que use `ano_referencia` e confie no
resultado vai escrever um relatório inteiro sobre "2024" analisando 20 anos de
dados.

**Como se proteger — faça isto sempre:**

```python
# 1) Meça o total SEM filtro.
total_sem_filtro = requests.get(base, timeout=60, verify=False).json()["count"]

# 2) Meça COM o filtro.
total_com_filtro = requests.get(base, params={"ano_referencia": 2024},
                                timeout=60, verify=False).json()["count"]

# 3) Se forem iguais, o filtro não existe.
if total_com_filtro == total_sem_filtro:
    raise ValueError("o filtro foi ignorado pela API — confira o nome do campo")
```

E confirme sempre uma amostra do resultado:

```python
amostra = resposta.json()["results"][0]
print(amostra["data"], amostra["ano_referencia"])   # é o período que você pediu?
```

### 5.4 A hierarquia que conta o mesmo dinheiro várias vezes

**Sintoma:** você soma a coluna de valor arrecadado e obtém um número
absurdamente maior que o orçamento do município.

**Causa:** a listagem de receitas traz **todos os níveis da árvore contábil**.
A linha "RECEITAS CORRENTES" (código `1.0.0.0.00.0.0`) é o agregado das linhas
abaixo dela, que por sua vez agregam as suas. Somar tudo conta o mesmo real
cinco, seis, sete vezes.

Na coleta de 2025 analisada neste PoC, a soma ingênua deu **R$ 21,69 bilhões**
contra **R$ 3,28 bilhões** reais — um fator de **6,6 vezes**.

**Solução:** identifique o nível pelo código e some apenas um nível.

```python
def nivel_hierarquico(codigo):
    """Conta quantos segmentos significativos o código tem antes dos zeros."""
    niveis = 0
    for parte in str(codigo).split("."):
        if parte.strip("0") == "":      # segmento só de zeros: acabou
            break
        niveis += 1
    return niveis

# Para o total do município, use apenas a raiz:
raiz = df[df["descricao"].isin(["RECEITAS CORRENTES", "RECEITAS DE CAPITAL"])]
total_correto = raiz["valor_arrecado_mes"].sum()

# Para analisar composição, escolha UM nível e fique nele:
nivel_3 = df[df["codigo"].map(nivel_hierarquico) == 3]
```

### 5.5 Os totais mudam — e nem sempre crescem

Comparando as medições deste PoC:

| Módulo | Agosto/2026 | Outubro/2026 | Variação |
|---|---|---|---|
| Receitas | 176.993 | 180.976 | +3.983 |
| Despesas | 1.545 | 3.412 | +1.867 |
| Licitações | 2.129 | 2.161 | +32 |
| Contratos | 8.936 | 8.897 | **−39** |
| Servidores | 28.577 | 16.116 | **−12.461** |

Servidores **caiu 44%** em dois meses. A explicação mais provável é mudança no
critério de publicação (por exemplo, passar a listar apenas vínculos ativos) —
mas o ponto para você é outro: **a base não é um arquivo imutável**.

Consequências práticas:

- **Registre a data de coleta** em todo resultado que você reportar.
- **Guarde o arquivo baixado.** Não conte com rebaixar e obter o mesmo.
- Se um número seu não bate com o do colega, **compare as datas de coleta antes
  de procurar erro no código**.

---

## 6. Robustez: não perca duas horas de download

Downloads longos falham. Aconteceu durante a construção deste PoC: a coleta
morreu na página 2.425 de 3.444, por timeout do servidor — e perdeu tudo,
porque o script só salvava no final.

Três medidas resolvem, em ordem de importância:

### 6.1 Gravação incremental

**A mais importante.** Escreva cada página no arquivo assim que ela chega. Não
acumule tudo na memória para salvar no fim.

```python
import csv

with open("receitas.csv", "w", newline="", encoding="utf-8-sig") as arquivo:
    escritor = None
    for pagina in paginas():
        if escritor is None:
            escritor = csv.DictWriter(arquivo, fieldnames=list(pagina[0].keys()),
                                      delimiter=";", extrasaction="ignore")
            escritor.writeheader()
        escritor.writerows(pagina)
        arquivo.flush()          # força a escrita em disco agora
```

### 6.2 Checkpoint para retomar

Guarde onde parou. Ao reiniciar, continue dali.

```python
import json
import os

def salvar_checkpoint(offset, caminho="coleta.checkpoint"):
    """Grava em arquivo temporário e renomeia: a troca é atômica no sistema."""
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)
    os.replace(temporario, caminho)
```

> **Por que o arquivo temporário?** Se o processo morrer **durante** a escrita do
> checkpoint, o arquivo fica cortado no meio e ilegível — e você perde a
> capacidade de retomar, que era justamente o ponto. Aconteceu neste projeto:
> um checkpoint de 236 MB corrompeu e exigiu recuperar os registros parseando o
> JSON truncado. Escrever em temporário e renomear elimina esse risco, porque a
> renomeação é instantânea para o sistema de arquivos.

### 6.3 Retry com espera crescente

Falha de rede costuma ser passageira. Tente de novo, esperando cada vez mais.

```python
import time

def get_com_retry(sessao, url, tentativas=5, **kwargs):
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = sessao.get(url, timeout=60, **kwargs)
            resposta.raise_for_status()
            return resposta
        except requests.exceptions.RequestException as erro:
            if tentativa == tentativas:
                raise
            espera = 3 * (2 ** (tentativa - 1))     # 3, 6, 12, 24, 48 s
            print(f"  falha ({erro.__class__.__name__}); "
                  f"tentativa {tentativa}/{tentativas}, aguardando {espera}s")
            time.sleep(espera)
```

---

## 7. Descobrindo endpoints não documentados

O portal novo não tem documentação. Todas as ações listadas na seção 3.3 foram
descobertas desta forma — e vale aprender a técnica, porque ela serve para
qualquer portal.

### Pelo navegador (mais simples)

1. Abra a página do módulo no navegador
2. Pressione **F12** → aba **Network** (Rede)
3. Filtre por **Fetch/XHR**
4. Navegue, pagine, filtre na página
5. Clique na requisição para `/api` e veja a aba **Payload**: o campo `acao` é o
   que você procura

### Pelo código-fonte da página

O portal carrega módulos JavaScript que contêm os nomes das ações. Foi assim que
encontrei a ação `sgreceitas/detalhes`, que não aparece na navegação comum:

```python
import re
import requests

NAVEGADOR = "Mozilla/5.0 ... Chrome/126.0.0.0 ..."

# 1) A página indica quais módulos JS carrega.
html = requests.get("https://acessoainformacao.palmas.to.gov.br/cidadao/transparencia/sgreceitas",
                    headers={"User-Agent": NAVEGADOR}, timeout=60).text
print(re.findall(r'CALL_JS\s*=\s*(\[[^\]]+\])', html))
# -> ["cidadao/controller/receitas/sgreceitas", ...]

# 2) Baixe o módulo e procure as chamadas à API.
js = requests.get("https://static.nucleogov.com.br/res/js/cidadao/controller/receitas/sgreceitas.js?v=5.4.79",
                  headers={"User-Agent": NAVEGADOR}, timeout=60).text
print(re.findall(r'setRequest\("([^"]+)",\s*"([^"]+)"', js))
# -> [('sgreceitas', 'detalhes'), ...]
```

### Testando um palpite

Ação inexistente responde `200` com a mensagem `"Ação não encontrada"` em vez de
um objeto — não dá erro HTTP. Teste assim:

```python
def acao_existe(sessao, acao, referer):
    consulta = {"k1": {"order": {}, "limit": "0, 1", "acao": acao}}
    bloco = sessao.post(f"{BASE}/api",
                        data={"multi_request": "true", "params": json.dumps(consulta)},
                        headers=cabecalhos(referer), timeout=60).json()["k1"]
    if isinstance(bloco, str):
        return False, bloco                      # "Ação não encontrada"
    return True, bloco.get("total")
```

Resultados reais desta função:

| Ação testada | Retorno | Leitura |
|---|---|---|
| `sgreceitas/listar` | `(True, 180976)` | existe e tem dados |
| `sgreceitas/detalhes` | `(True, 0)` | **existe, mas exige parâmetros** |
| `sgreceitas/inventada` | `(False, 'Ação não encontrada')` | não existe |

Observe a linha do meio: total zero **não** significa que a ação não serve.
`detalhes` precisa de `ano`, `mes`, `codigo` e `orgao` para devolver algo — sem
eles, responde vazio. Distinga sempre os três casos: ação inexistente (vem
texto), ação que exige parâmetros (vem zero) e módulo realmente sem dados
publicados (também vem zero, mas com qualquer parâmetro).

**Exemplo do que isso rende:** a ação `sgreceitas/detalhes` abre a **movimentação
diária** de cada linha de receita, com os parâmetros `ano`, `mes`, `codigo`
(use o campo `codigo_original`) e `orgao`. Uma linha mensal de receita se abre
em centenas de lançamentos diários — um nível de detalhe que não existe na
listagem comum.

---

## 8. Checklist antes de entregar

Confira cada item antes de considerar a Sprint 2 concluída:

**Coleta**

- [ ] O script tem `timeout` em todas as requisições
- [ ] Há pausa de pelo menos 0,3 s entre requisições
- [ ] A paginação foi seguida até o fim (o total conferido com o que a API informa)
- [ ] Há retry com espera crescente
- [ ] A gravação é incremental, com checkpoint atômico
- [ ] O script roda de novo sem recomeçar do zero

**Validação — a parte que diferencia os trabalhos**

- [ ] Cada filtro usado foi **comprovado** (total com filtro ≠ total sem filtro)
- [ ] O conteúdo de uma amostra foi inspecionado, não só a contagem
- [ ] A hierarquia de receitas foi tratada, se você somou valores
- [ ] A data de coleta está registrada no README e no nome do arquivo
- [ ] A contagem de linhas do arquivo final bate com o total informado pela API

**Documentação**

- [ ] O README informa a fonte, a data e o endpoint exato de cada arquivo
- [ ] As armadilhas que você encontrou estão documentadas
- [ ] As decisões discutíveis (como `verify=False` e o `User-Agent`) estão
      justificadas por escrito

**Ética**

- [ ] Nenhum dado pessoal identificável foi coletado
- [ ] Não há coleta em automação recorrente
- [ ] O `robots.txt` foi verificado

---

## Ponto de partida

Os scripts deste PoC são implementações completas do que este manual descreve:

| Arquivo | Serve de modelo para |
|---|---|
| `src/coleta.py` | Coleta no portal novo, com sessão, paginação e retry |
| `src/etl.py` | Limpeza, tipagem e carga no banco (inclui o tratamento da hierarquia) |
| `notebooks/eda_sprint2.ipynb` | Análise exploratória, com a demonstração da dupla contagem |

Copie o padrão, não o arquivo: o valor da sprint está em você entender por que
cada proteção existe. Toda armadilha desta página custou horas a alguém — e
agora custa a você apenas o tempo de leitura.
