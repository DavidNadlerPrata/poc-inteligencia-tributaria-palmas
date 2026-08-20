"""Configuracao central do PoC de Inteligencia Tributaria."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "data"
MODELOS = RAIZ / "models"
DOCS = RAIZ / "docs"

for _p in (DADOS, MODELOS):
    _p.mkdir(exist_ok=True)

# --------------------------- Fontes de dados ---------------------------
# Portal NUCLEOGOV (dados atuais, HTTPS). O WAF bloqueia User-Agent que nao
# pareca navegador real -- dai o UA de Chrome abaixo.
PORTAL_BASE = "https://acessoainformacao.palmas.to.gov.br"
PORTAL_API = PORTAL_BASE + "/api"
PORTAL_REFERER = PORTAL_BASE + "/cidadao/transparencia/sgreceitas"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Boas praticas de coleta (secao 11 do plano de ensino): carga razoavel no servidor.
PAUSA_REQUISICAO = 0.3
TIMEOUT = 90
MAX_TENTATIVAS = 5

# --------------------------- Banco de dados ---------------------------
BANCO = DADOS / "inteligencia_tributaria.db"

# --------------------------- Arquivos gerados ---------------------------
CSV_ARRECADACAO = DADOS / "arrecadacao_bruta.csv"
CSV_CARTEIRA = DADOS / "carteira_contribuintes.csv"
MODELO_INADIMPLENCIA = MODELOS / "modelo_inadimplencia.joblib"
MODELO_RECUPERABILIDADE = MODELOS / "modelo_recuperabilidade.joblib"
METRICAS = MODELOS / "metricas.json"

# --------------------------- Parametros do dominio ---------------------------
# Fontes: Sefin/Palmas e Conexao Tocantins (jun/2026), citados no plano de ensino.
DIVIDA_ATIVA_TOTAL = 894_000_000.0   # R$ 894 milhoes
DIVIDA_IPTU = 363_000_000.0          # R$ 363 milhoes
DIVIDA_ISS = 380_000_000.0           # R$ 380 milhoes
IMOVEIS_TRIBUTAVEIS = 111_252
META_ADIMPLENCIA = 0.67              # 74.606 contribuintes

# Tamanho da carteira simulada no PoC (amostra dos imoveis tributaveis).
TAMANHO_AMOSTRA = 20_000
SEMENTE = 42

# Setores urbanos de Palmas usados na simulacao, com faixa de renda
# predominante (proxy do setor censitario do IBGE) e peso populacional.
SETORES_URBANOS = [
    # (nome, faixa_renda, peso, fator_valor_venal)
    ("Plano Diretor Norte",       "alta",   0.14, 1.55),
    ("Plano Diretor Sul",         "media",  0.22, 1.00),
    ("Taquaralto",                "baixa",  0.20, 0.55),
    ("Aureny",                    "baixa",  0.18, 0.50),
    ("Taquari",                   "baixa",  0.08, 0.45),
    ("Setor Comercial Central",   "alta",   0.06, 1.90),
    ("Jardim Aureny IV",          "media",  0.07, 0.70),
    ("Area de Expansao",          "media",  0.05, 0.80),
]

TIPOS_IMOVEL = ["residencial", "comercial", "terreno", "industrial"]

# Grupos protegidos pelo IPTU Social de Palmas: idosos, aposentados,
# pensionistas e PCD de baixa renda. Devem ser EXCLUIDOS das acoes preditivas
# de cobranca (secao 11 do plano de ensino).
PROPORCAO_IPTU_SOCIAL = 0.08
