"""
Dashboard de Carteira - Ações de Longo Prazo e Dividendos
Streamlit + yfinance
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# ------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Carteira | Dividendos & Longo Prazo",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# CSS - TEMA ESCURO / CARTÕES
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #1a1d24;
        border-radius: 12px;
        padding: 18px;
        border: 1px solid #2a2d34;
        margin-bottom: 10px;
    }
    .alert-card-green {
        background-color: #0f2418;
        border-left: 5px solid #00c853;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .alert-card-yellow {
        background-color: #2b230f;
        border-left: 5px solid #ffb300;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .alert-card-red {
        background-color: #2b0f0f;
        border-left: 5px solid #ff5252;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 22px;
    }
    thead tr th {
        background-color: #1a1d24 !important;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# CARTEIRA PRÉ-DEFINIDA
# ------------------------------------------------------------------
PORTFOLIO = [
    {"nome": "Alphabet",         "ticker": "GOOGL",   "peso": 10, "setor": "Tecnologia"},
    {"nome": "JPMorgan Chase",   "ticker": "JPM",     "peso": 10, "setor": "Financeiro"},
    {"nome": "Mastercard",       "ticker": "MA",      "peso": 7,  "setor": "Financeiro"},
    {"nome": "Starbucks",        "ticker": "SBUX",    "peso": 5,  "setor": "Consumo Discricionário"},
    {"nome": "Walt Disney",      "ticker": "DIS",     "peso": 5,  "setor": "Consumo Discricionário"},
    {"nome": "PepsiCo",          "ticker": "PEP",     "peso": 6,  "setor": "Consumo Básico"},
    {"nome": "Realty Income",    "ticker": "O",       "peso": 6,  "setor": "Imobiliário (REIT)"},
    {"nome": "Ecolab",           "ticker": "ECL",     "peso": 6,  "setor": "Industrial"},
    {"nome": "Zoetis",           "ticker": "ZTS",     "peso": 5,  "setor": "Saúde"},
    {"nome": "Novo Nordisk",     "ticker": "NVO",     "peso": 5,  "setor": "Saúde"},
    {"nome": "UnitedHealth",     "ticker": "UNH",     "peso": 5,  "setor": "Saúde"},
    {"nome": "Munich Re",        "ticker": "MUV2.DE", "peso": 5,  "setor": "Financeiro (Seguros)"},
    {"nome": "Cameco Corp",      "ticker": "CCJ",     "peso": 5,  "setor": "Energia/Materiais"},
    {"nome": "Vistra Corp",      "ticker": "VST",     "peso": 5,  "setor": "Utilities"},
    {"nome": "Caterpillar",      "ticker": "CAT",     "peso": 5,  "setor": "Industrial"},
    {"nome": "Procter & Gamble", "ticker": "PG",      "peso": 4,  "setor": "Consumo Básico"},
    {"nome": "Mondelez",         "ticker": "MDLZ",    "peso": 3,  "setor": "Consumo Básico"},
    {"nome": "NextEra Energy",   "ticker": "NEE",     "peso": 3,  "setor": "Utilities"},
    {"nome": "American Water Works", "ticker": "AWK", "peso": 3, "setor": "Utilities"},
]

TICKERS = [a["ticker"] for a in PORTFOLIO]

# ------------------------------------------------------------------
# BANDAS DE REFERÊNCIA POR SETOR
# ------------------------------------------------------------------
# Critério usado por casas de research (ex: Morningstar, Seeking Alpha Quant):
# comparar cada rácio com a média típica do PRÓPRIO setor, não com um valor fixo
# igual para toda a carteira — um P/E de 25 é caro para um banco mas barato
# para uma tech. Cada lista [c0, c1, c2] define os cortes ascendentes usados
# em _pontos_metrica (ver função abaixo). Valores indicativos, baseados em
# médias históricas de mercado por setor — não substituem research atualizado.
SECTOR_BENCHMARKS = {
    "Tecnologia": {
        "pe": [20, 30, 40], "pb": [4, 8, 12],
        "growth": [5, 12, 20], "roe": [15, 22, 30], "margin": [12, 20, 28], "roic": [12, 18, 26],
        "payout": [30, 50, 70], "debt": [30, 70, 120],
        "fcf_payout": [40, 70, 100], "interest_coverage": [5, 10, 20],
    },
    "Financeiro": {
        "pe": [9, 12, 16], "pb": [1.0, 1.8, 2.5],
        "growth": [2, 6, 10], "roe": [8, 12, 16], "margin": [15, 22, 30], "roic": [4, 7, 11],
        "payout": [40, 60, 80], "debt": [300, 500, 700],
        # Bancos não têm "FCF" nem "cobertura de juros" no sentido tradicional
        # (a dívida É o produto); bandas muito largas para não distorcer a nota
        "fcf_payout": [50, 80, 120], "interest_coverage": [1, 2, 4],
    },
    "Financeiro (Seguros)": {
        "pe": [8, 11, 14], "pb": [0.9, 1.5, 2.2],
        "growth": [2, 5, 9], "roe": [7, 11, 15], "margin": [8, 14, 20], "roic": [4, 7, 11],
        "payout": [40, 60, 80], "debt": [300, 500, 700],
        "fcf_payout": [50, 80, 120], "interest_coverage": [1, 2, 4],
    },
    "Consumo Discricionário": {
        "pe": [15, 22, 30], "pb": [2.5, 4.5, 7],
        "growth": [3, 8, 14], "roe": [10, 16, 24], "margin": [4, 8, 14], "roic": [8, 13, 20],
        "payout": [30, 50, 70], "debt": [40, 80, 140],
        "fcf_payout": [40, 70, 100], "interest_coverage": [3, 6, 12],
    },
    "Consumo Básico": {
        "pe": [16, 21, 26], "pb": [3, 6, 9],
        "growth": [0, 4, 8], "roe": [15, 22, 30], "margin": [6, 11, 16], "roic": [10, 16, 24],
        "payout": [50, 65, 80], "debt": [50, 90, 150],
        "fcf_payout": [60, 80, 100], "interest_coverage": [4, 8, 15],
    },
    "Imobiliário (REIT)": {
        "pe": [14, 19, 25], "pb": [1.2, 1.8, 2.5],
        "growth": [-2, 3, 7], "roe": [4, 7, 11], "margin": [15, 25, 35], "roic": [3, 5, 8],
        # REITs são obrigados por lei a distribuir ~90%+ dos lucros, por isso
        # um payout alto aqui é normal e não é sinal de perigo como noutros setores
        "payout": [75, 90, 100], "debt": [80, 150, 220],
        "fcf_payout": [90, 110, 140], "interest_coverage": [2, 3.5, 6],
    },
    "Industrial": {
        "pe": [14, 19, 24], "pb": [2.5, 4.5, 7],
        "growth": [0, 6, 12], "roe": [10, 16, 22], "margin": [5, 10, 15], "roic": [7, 12, 18],
        "payout": [35, 55, 75], "debt": [50, 100, 160],
        "fcf_payout": [45, 75, 105], "interest_coverage": [3, 6, 12],
    },
    "Saúde": {
        "pe": [14, 20, 27], "pb": [3, 5.5, 8],
        "growth": [2, 8, 15], "roe": [10, 16, 24], "margin": [6, 12, 18], "roic": [7, 13, 20],
        "payout": [35, 55, 75], "debt": [40, 80, 130],
        "fcf_payout": [45, 75, 105], "interest_coverage": [4, 8, 15],
    },
    "Energia/Materiais": {
        "pe": [7, 11, 16], "pb": [1.2, 2.2, 3.5],
        "growth": [-5, 3, 10], "roe": [5, 10, 16], "margin": [5, 12, 20], "roic": [4, 8, 13],
        "payout": [30, 50, 70], "debt": [40, 80, 140],
        "fcf_payout": [40, 70, 100], "interest_coverage": [3, 6, 12],
    },
    "Utilities": {
        "pe": [14, 18, 23], "pb": [1.5, 2.2, 3],
        "growth": [-1, 2, 5], "roe": [7, 10, 14], "margin": [6, 10, 15], "roic": [4, 7, 11],
        # Utilities financiam-se estruturalmente com mais dívida (negócio regulado
        # e previsível), por isso as bandas são mais permissivas que a média.
        # O FCF é tipicamente pressionado por capex pesado (redes, infraestrutura),
        # por isso um FCF Payout >100% é comum e não é, por si só, alarmante.
        "payout": [55, 70, 85], "debt": [90, 150, 220],
        "fcf_payout": [80, 110, 150], "interest_coverage": [2, 3.5, 6],
    },
    # Aplicado quando o setor não está mapeado acima
    "_default": {
        "pe": [15, 20, 30], "pb": [2, 4, 6],
        "growth": [0, 8, 15], "roe": [5, 12, 20], "margin": [5, 12, 20], "roic": [4, 9, 15],
        "payout": [40, 60, 80], "debt": [50, 100, 160],
        "fcf_payout": [50, 80, 110], "interest_coverage": [3, 6, 12],
    },
}

# ------------------------------------------------------------------
# FUNÇÕES DE APOIO
# ------------------------------------------------------------------

def formata_grande(valor):
    """Formata capitalização bolsista em B/T."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "N/D"
    if valor >= 1e12:
        return f"{valor/1e12:.2f} T"
    if valor >= 1e9:
        return f"{valor/1e9:.2f} B"
    if valor >= 1e6:
        return f"{valor/1e6:.2f} M"
    return f"{valor:.0f}"


def formata_pct(valor, casas=2):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "N/D"
    return f"{valor:.{casas}f}%"


@st.cache_data(ttl=900, show_spinner=False)
def obter_dados(ticker, tentativas=2):
    """Vai buscar dados fundamentais e de mercado a um ticker via yfinance.
    Tenta novamente (com uma pequena pausa) se o pedido falhar — o Yahoo Finance
    aplica rate limiting a IPs que fazem muitos pedidos seguidos (comum em
    plataformas cloud partilhadas como o Streamlit Cloud), e muitas destas
    falhas são temporárias."""
    for tentativa in range(tentativas):
        try:
            t = yf.Ticker(ticker)
            info = t.info

            # Pede 5 anos de histórico de uma vez só (serve para o preço, para o
            # mínimo/máximo de 52 semanas E para calcular o yield médio histórico)
            hist_5y = t.history(period="5y")
            if hist_5y.empty:
                raise ValueError("Histórico de preços vazio (possível rate limit do Yahoo Finance)")
            hist_1y = hist_5y[hist_5y.index >= (hist_5y.index.max() - pd.Timedelta(days=365))]

            preco_atual = info.get("currentPrice") or info.get("regularMarketPrice") or hist_1y["Close"].iloc[-1]
            fecho_anterior = info.get("previousClose") or (hist_1y["Close"].iloc[-2] if len(hist_1y) > 1 else preco_atual)
            variacao_pct = ((preco_atual - fecho_anterior) / fecho_anterior) * 100 if fecho_anterior else np.nan

            pe_ratio = info.get("trailingPE", np.nan)
            dividend_rate_bruto = info.get("dividendRate", np.nan)  # usado mais à frente (yield e FCF payout)

            market_cap = info.get("marketCap", np.nan)

            low_52 = info.get("fiftyTwoWeekLow", hist_1y["Low"].min())
            high_52 = info.get("fiftyTwoWeekHigh", hist_1y["High"].max())

            dist_do_minimo = ((preco_atual - low_52) / low_52) * 100 if low_52 else np.nan
            dist_do_maximo = ((high_52 - preco_atual) / high_52) * 100 if high_52 else np.nan

            nome_completo = info.get("shortName", ticker)

            # ---- rácios extra para os Factor Grades ----
            price_to_book = info.get("priceToBook", np.nan)
            revenue_growth = info.get("revenueGrowth", np.nan)   # fração, ex: 0.12 = 12%
            earnings_growth = info.get("earningsGrowth", np.nan)  # fração
            roe = info.get("returnOnEquity", np.nan)              # fração
            profit_margin = info.get("profitMargins", np.nan)     # fração
            peg_ratio = info.get("trailingPegRatio") or info.get("pegRatio", np.nan)

            # ---- rácios extra para o Dividend Safety Score ----
            payout_raw = info.get("payoutRatio", np.nan)
            payout_ratio = payout_raw * 100 if pd.notna(payout_raw) else np.nan  # fração -> %
            debt_to_equity = info.get("debtToEquity", np.nan)  # já vem como % (ex: 120 = D/E de 1,2x)

            anos_consecutivos, dividend_cagr_5y, yield_medio_5anos, ttm_dividendo_atual = \
                calcular_metricas_dividendo(t, hist_5y)

            # ---- Dividend Yield atual: TTM (últimos 12 meses pagos, real) ÷ preço ----
            # Fonte primária: dados de dividendos efetivamente pagos (mesma base de
            # cálculo do "yield médio 5 anos", por consistência). Isto evita confiar
            # no campo "dividendYield" do yfinance, cujo formato mudou consoante a
            # versão/ticker e já causou casos absurdos (ex: 58% ou 80% numa ação que
            # paga na realidade menos de 1%).
            if pd.notna(ttm_dividendo_atual) and ttm_dividendo_atual > 0 and preco_atual:
                dividend_yield = (ttm_dividendo_atual / preco_atual) * 100
            elif pd.notna(dividend_rate_bruto) and dividend_rate_bruto and preco_atual:
                dividend_yield = (dividend_rate_bruto / preco_atual) * 100
            else:
                div_yield_raw = info.get("dividendYield", None)
                if div_yield_raw is None:
                    dividend_yield = np.nan
                else:
                    candidato = div_yield_raw * 100 if div_yield_raw < 1 else div_yield_raw
                    dividend_yield = candidato if candidato < 25 else np.nan

            # ---- FCF Payout Ratio: dividendos totais pagos vs. Free Cash Flow ----
            # Mais rigoroso que o payout contabilístico, porque usa dinheiro real gerado,
            # não o lucro (que pode ter itens não-monetários como amortizações/imparidades).
            dividend_rate = dividend_rate_bruto  # dividendo anual por ação, reutilizado do cálculo do yield
            fcf_payout_ratio = np.nan             # também para o Valor Intrínseco
            try:
                fcf = info.get("freeCashflow")
                shares_out = info.get("sharesOutstanding")
                if fcf and pd.notna(dividend_rate) and dividend_rate and shares_out and fcf > 0:
                    dividendos_totais = dividend_rate * shares_out
                    fcf_payout_ratio = (dividendos_totais / fcf) * 100
            except Exception:
                pass

            # ---- Beta e Forward P/E: indicadores complementares, mostrados como informação ----
            beta = info.get("beta", np.nan)
            forward_pe = info.get("forwardPE", np.nan)

            # ---- Interest Coverage Ratio: EBIT / Despesa com Juros ----
            # Mede quantas vezes o lucro operacional cobre os juros da dívida.
            # Quanto mais alto, mais folgada é a empresa para pagar a dívida sem
            # comprometer o dividendo. Vem da demonstração de resultados anual.
            # Falhas aqui NUNCA fazem perder os dados principais (preço, P/E, etc.):
            # calcular_interest_coverage já devolve N/D em vez de rebentar.
            interest_coverage = calcular_interest_coverage(t)

            # ---- ROIC: retorno sobre TODO o capital investido (dívida + capital próprio) ----
            # Mesma lógica: se falhar, devolve N/D sem afetar o resto dos dados.
            roic = calcular_roic(t)

            return {
                "nome_completo": nome_completo,
                "preco": preco_atual,
                "variacao_pct": variacao_pct,
                "pe_ratio": pe_ratio,
                "dividend_yield": dividend_yield,
                "market_cap": market_cap,
                "low_52": low_52,
                "high_52": high_52,
                "dist_do_minimo": dist_do_minimo,
                "dist_do_maximo": dist_do_maximo,
                "moeda": info.get("currency", ""),
                "price_to_book": price_to_book,
                "revenue_growth": revenue_growth,
                "earnings_growth": earnings_growth,
                "roe": roe,
                "profit_margin": profit_margin,
                "peg_ratio": peg_ratio,
                "payout_ratio": payout_ratio,
                "debt_to_equity": debt_to_equity,
                "anos_consecutivos_crescimento": anos_consecutivos,
                "dividend_cagr_5y": dividend_cagr_5y,
                "yield_medio_5anos": yield_medio_5anos,
                "fcf_payout_ratio": fcf_payout_ratio,
                "beta": beta,
                "forward_pe": forward_pe,
                "interest_coverage": interest_coverage,
                "roic": roic,
                "dividend_rate": dividend_rate,
            }
        except Exception as e:
            if tentativa < tentativas - 1:
                time.sleep(1.5)  # pausa antes de tentar de novo (dá tempo ao rate limit passar)
                continue
            return {"erro": str(e)}


def calcular_interest_coverage(t):
    """Calcula o Interest Coverage Ratio (EBIT / Despesa com Juros) a partir da
    demonstração de resultados anual. Usa 'Operating Income' como aproximação
    ao EBIT (rubrica mais fiável e consistente no yfinance) e procura a despesa
    de juros entre os nomes mais comuns dessa rubrica. Devolve N/D em vez de
    rebentar sempre que a informação não estiver disponível (ex: alguns bancos)."""
    try:
        financials = t.financials
        if financials is None or financials.empty:
            return np.nan

        def _primeira_linha(candidatos):
            for nome in candidatos:
                if nome in financials.index:
                    valor = financials.loc[nome].iloc[0]
                    if pd.notna(valor):
                        return valor
            return None

        ebit = _primeira_linha(["EBIT", "Operating Income"])
        interest_expense = _primeira_linha(
            ["Interest Expense", "Interest Expense Non Operating", "Net Interest Income"]
        )

        if ebit is None or interest_expense in (None, 0):
            return np.nan

        return abs(ebit / interest_expense)
    except Exception:
        return np.nan


def calcular_roic(t):
    """Calcula o ROIC (Return on Invested Capital): NOPAT / Capital Investido.
    Ao contrário do ROE (que só olha para o capital próprio e pode ser
    'inflacionado' por dívida), o ROIC mede o retorno sobre TODO o capital
    usado no negócio — dívida + capital próprio — dando uma imagem mais
    fiel da qualidade real do negócio, independente de como é financiado.
      NOPAT = Resultado Operacional × (1 - taxa de imposto efetiva)
      Capital Investido = Dívida Total + Capital Próprio - Caixa
    Devolve N/D sempre que faltar alguma rubrica (comum em bancos/seguradoras,
    onde o conceito de "capital investido" tradicional não se aplica bem)."""
    try:
        fin = t.financials
        bs = t.balance_sheet
        if fin is None or fin.empty or bs is None or bs.empty:
            return np.nan

        def _primeira(df, candidatos):
            for nome in candidatos:
                if nome in df.index:
                    valor = df.loc[nome].iloc[0]
                    if pd.notna(valor):
                        return valor
            return None

        operating_income = _primeira(fin, ["Operating Income", "EBIT"])
        if operating_income is None:
            return np.nan

        # Taxa de imposto efetiva (com fallback para a taxa federal dos EUA, 21%)
        pretax_income = _primeira(fin, ["Pretax Income"])
        tax_provision = _primeira(fin, ["Tax Provision"])
        if pretax_income and tax_provision is not None and pretax_income != 0:
            taxa_imposto = min(max(tax_provision / pretax_income, 0), 0.5)
        else:
            taxa_imposto = 0.21

        nopat = operating_income * (1 - taxa_imposto)

        total_debt = _primeira(bs, ["Total Debt"])
        equity = _primeira(bs, ["Stockholders Equity", "Common Stock Equity",
                                 "Total Equity Gross Minority Interest"])
        cash = _primeira(bs, ["Cash And Cash Equivalents",
                               "Cash Cash Equivalents And Short Term Investments"]) or 0

        if total_debt is None or equity is None:
            return np.nan

        capital_investido = total_debt + equity - cash
        if capital_investido <= 0:
            return np.nan

        return (nopat / capital_investido) * 100
    except Exception:
        return np.nan


def calcular_metricas_dividendo(t, hist_5y):
    """Calcula, a partir do histórico de pagamentos de dividendos:
    - anos consecutivos de aumento do dividendo
    - CAGR (taxa de crescimento anual composta) do dividendo nos últimos ~5 anos
    - yield médio dos últimos 5 anos
    Devolve (np.nan, np.nan, np.nan) se a empresa não pagar dividendos ou os dados forem insuficientes.

    MÉTODO: compara sempre o pagamento mais recente com o pagamento mais próximo
    de "~1 ano antes" (dentro de uma margem de ~60 dias), em vez de somar por ano
    civil ou usar um ponto fixo exato a 365 dias. Isto evita dois problemas reais:
    1) empresas que aumentam o dividendo a meio do ano civil (ex: PepsiCo) não
       ficam com anos "contaminados" por trimestres a taxas diferentes;
    2) pequenas variações de 1-2 dias no calendário de pagamentos (comum, ex:
       Caterpillar) não fazem uma comparação exata a 365 dias falhar por pouco."""
    try:
        divs = t.dividends
        if divs is None or divs.empty:
            return np.nan, np.nan, np.nan, np.nan

        divs = divs.sort_index()
        if divs.index.tz is not None:
            divs = divs.copy()
            divs.index = divs.index.tz_localize(None)

        datas = divs.index
        valores = divs.values
        if len(valores) < 2:
            return np.nan, np.nan, np.nan, np.nan

        def _pagamento_mais_proximo(data_alvo, limite_superior_idx, margem_dias):
            """Encontra, entre os pagamentos anteriores a limite_superior_idx, o mais
            próximo de data_alvo, desde que dentro da margem_dias. Devolve o índice ou None."""
            pos = datas.searchsorted(data_alvo)
            melhor_idx, melhor_diff = None, None
            for p in (pos - 1, pos):
                if 0 <= p < limite_superior_idx:
                    diff = abs((datas[p] - data_alvo).days)
                    if diff <= margem_dias and (melhor_diff is None or diff < melhor_diff):
                        melhor_idx, melhor_diff = p, diff
            return melhor_idx

        # ---- anos consecutivos: recua pagamento a pagamento (~1 ano de cada vez) ----
        anos_consecutivos = 0
        idx_atual = len(valores) - 1
        for _ in range(25):  # limite de segurança
            data_alvo = datas[idx_atual] - pd.DateOffset(days=350)
            idx_anterior = _pagamento_mais_proximo(data_alvo, idx_atual, margem_dias=60)
            if idx_anterior is None:
                break
            if valores[idx_atual] >= valores[idx_anterior] * 0.999:  # tolerância a arredondamentos
                anos_consecutivos += 1
                idx_atual = idx_anterior
            else:
                break

        # ---- CAGR do dividendo: pagamento mais recente vs. pagamento mais próximo de há ~5 anos ----
        dividend_cagr_5y = np.nan
        data_alvo_5y = datas[-1] - pd.DateOffset(days=5 * 365)
        idx_5y = _pagamento_mais_proximo(data_alvo_5y, len(valores) - 1, margem_dias=90)
        if idx_5y is not None and valores[idx_5y] > 0:
            dividend_cagr_5y = (valores[-1] / valores[idx_5y]) ** (1 / 5) - 1

        # ---- yield médio dos últimos 5 anos: TTM dividendo / preço, em cada dia ----
        ttm = divs.rolling("365D").sum()
        precos = hist_5y["Close"]
        if precos.index.tz is not None:
            precos = precos.copy()
            precos.index = precos.index.tz_localize(None)
        ttm_diario = ttm.reindex(precos.index, method="ffill")
        yields_diarios = (ttm_diario / precos).dropna()
        yield_medio_5anos = yields_diarios.mean() * 100 if not yields_diarios.empty else np.nan

        # TTM mais recente (últimos 12 meses de dividendos efetivamente pagos) — fonte
        # fiável e sem ambiguidade de formato, usada para calcular o Dividend Yield atual
        ttm_atual = ttm.iloc[-1] if not ttm.empty else np.nan

        return anos_consecutivos, dividend_cagr_5y, yield_medio_5anos, ttm_atual
    except Exception:
        return np.nan, np.nan, np.nan, np.nan


@st.cache_data(ttl=900, show_spinner=False)
def carregar_carteira():
    linhas = []
    for i, ativo in enumerate(PORTFOLIO):
        dados = obter_dados(ativo["ticker"])
        # Pequena pausa entre pedidos (só quando não veio da cache) para não
        # disparar o rate limiting do Yahoo Finance com pedidos em rajada
        if i < len(PORTFOLIO) - 1:
            time.sleep(0.3)
        linha = {**ativo}
        if dados and "erro" not in dados:
            linha.update(dados)
        else:
            linha.update({
                "nome_completo": ativo["nome"], "preco": np.nan, "variacao_pct": np.nan,
                "pe_ratio": np.nan, "dividend_yield": np.nan, "market_cap": np.nan,
                "low_52": np.nan, "high_52": np.nan, "dist_do_minimo": np.nan,
                "dist_do_maximo": np.nan, "moeda": "",
                "price_to_book": np.nan, "revenue_growth": np.nan,
                "earnings_growth": np.nan, "roe": np.nan, "profit_margin": np.nan,
                "peg_ratio": np.nan, "payout_ratio": np.nan, "debt_to_equity": np.nan,
                "anos_consecutivos_crescimento": np.nan, "dividend_cagr_5y": np.nan,
                "yield_medio_5anos": np.nan, "fcf_payout_ratio": np.nan,
                "beta": np.nan, "forward_pe": np.nan, "interest_coverage": np.nan,
                "roic": np.nan, "dividend_rate": np.nan,
            })
        linhas.append(linha)
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------
# FACTOR GRADES (A-D) E QUANT RATING
# ------------------------------------------------------------------

def _pontos_metrica(valor, cortes, maior_melhor=True):
    """Converte um rácio num score de 1 a 4 com base em 3 cortes ascendentes.
    Se o valor não existir, devolve 2.0 (neutro) para não penalizar dados em falta."""
    if valor is None or pd.isna(valor):
        return 2.0
    c0, c1, c2 = cortes
    if maior_melhor:
        if valor >= c2:
            return 4.0
        elif valor >= c1:
            return 3.0
        elif valor >= c0:
            return 2.0
        return 1.0
    else:
        if valor <= c0:
            return 4.0
        elif valor <= c1:
            return 3.0
        elif valor <= c2:
            return 2.0
        return 1.0


def _nota_de_score(score):
    """Converte um score médio (1-4) numa nota de letra A-D."""
    if score >= 3.5:
        return "A"
    elif score >= 2.5:
        return "B"
    elif score >= 1.5:
        return "C"
    return "D"


def calcular_factor_grades(row):
    """Calcula as notas de Valuation, Growth e Profitability e o Quant Rating de uma linha,
    usando bandas de referência específicas do setor do ativo (critério profissional:
    o mesmo P/E significa coisas diferentes em setores diferentes)."""
    bandas = SECTOR_BENCHMARKS.get(row.get("setor"), SECTOR_BENCHMARKS["_default"])

    # ---- Valuation: P/E, P/B (mais baixos = melhor) + PEG (crescimento já embutido) ----
    componentes_valuation = [
        _pontos_metrica(row.get("pe_ratio"), bandas["pe"], maior_melhor=False),
        _pontos_metrica(row.get("price_to_book"), bandas["pb"], maior_melhor=False),
    ]
    peg = row.get("peg_ratio")
    if pd.notna(peg) and peg > 0:
        # PEG < 1 é considerado subvalorizado face ao crescimento; regra transversal a setores
        componentes_valuation.append(_pontos_metrica(peg, [1, 2, 3], maior_melhor=False))
    score_valuation = np.mean(componentes_valuation)

    # ---- Growth: crescimento de receita e de resultados (valores em %), vs. banda do setor ----
    receita_pct = row.get("revenue_growth") * 100 if pd.notna(row.get("revenue_growth")) else np.nan
    resultados_pct = row.get("earnings_growth") * 100 if pd.notna(row.get("earnings_growth")) else np.nan
    score_growth = np.mean([
        _pontos_metrica(receita_pct, bandas["growth"], maior_melhor=True),
        _pontos_metrica(resultados_pct, bandas["growth"], maior_melhor=True),
    ])

    # ---- Profitability: ROE, margem líquida e ROIC (valores em %), vs. banda do setor ----
    roe_pct = row.get("roe") * 100 if pd.notna(row.get("roe")) else np.nan
    margem_pct = row.get("profit_margin") * 100 if pd.notna(row.get("profit_margin")) else np.nan
    componentes_profitability = [
        _pontos_metrica(roe_pct, bandas["roe"], maior_melhor=True),
        _pontos_metrica(margem_pct, bandas["margin"], maior_melhor=True),
    ]
    roic = row.get("roic")
    if pd.notna(roic):
        # ROIC mede o retorno sobre TODO o capital (dívida + capital próprio),
        # por isso é mais difícil de "inflacionar" com dívida do que o ROE sozinho
        componentes_profitability.append(_pontos_metrica(roic, bandas["roic"], maior_melhor=True))
    score_profitability = np.mean(componentes_profitability)

    score_quant = np.mean([score_valuation, score_growth, score_profitability])
    if score_quant >= 3.3:
        rating = "Strong Buy"
    elif score_quant >= 2.3:
        rating = "Buy"
    else:
        rating = "Hold"

    return pd.Series({
        "grade_valuation": _nota_de_score(score_valuation),
        "grade_growth": _nota_de_score(score_growth),
        "grade_profitability": _nota_de_score(score_profitability),
        "score_quant": score_quant,
        "quant_rating": rating,
    })


def aplicar_factor_grades(df):
    """Adiciona as colunas de Factor Grades e Quant Rating ao DataFrame da carteira."""
    notas = df.apply(calcular_factor_grades, axis=1)
    return pd.concat([df, notas], axis=1)


# ------------------------------------------------------------------
# DIVIDEND SAFETY SCORE (A-D)
# ------------------------------------------------------------------
# Este é o indicador mais importante para uma estratégia de dividend growth:
# não basta o dividendo ser alto, tem de ser SUSTENTÁVEL. Combina 4 sinais:
#   1) Payout Ratio    -> quanto do lucro é distribuído (vs. banda do setor)
#   2) Debt/Equity      -> quanta dívida a empresa tem (vs. banda do setor)
#   3) Anos consecutivos de aumento do dividendo -> histórico de disciplina
#   4) CAGR do dividendo a 5 anos -> ritmo real de crescimento do dividendo

def calcular_dividend_safety(row):
    bandas = SECTOR_BENCHMARKS.get(row.get("setor"), SECTOR_BENCHMARKS["_default"])

    componentes = [
        _pontos_metrica(row.get("payout_ratio"), bandas["payout"], maior_melhor=False),
        _pontos_metrica(row.get("fcf_payout_ratio"), bandas["fcf_payout"], maior_melhor=False),
        _pontos_metrica(row.get("debt_to_equity"), bandas["debt"], maior_melhor=False),
        _pontos_metrica(row.get("interest_coverage"), bandas["interest_coverage"], maior_melhor=True),
        _pontos_metrica(row.get("anos_consecutivos_crescimento"), [3, 6, 11], maior_melhor=True),
    ]
    cagr = row.get("dividend_cagr_5y")
    cagr_pct = cagr * 100 if pd.notna(cagr) else np.nan
    componentes.append(_pontos_metrica(cagr_pct, [0, 3, 7], maior_melhor=True))

    score = np.mean(componentes)
    nota = _nota_de_score(score)
    rotulo = {"A": "Muito Seguro", "B": "Saudável", "C": "Moderado", "D": "Atenção"}[nota]

    return pd.Series({
        "score_dividend_safety": score,
        "grade_dividend_safety": nota,
        "dividend_safety_label": rotulo,
    })


def aplicar_dividend_safety(df):
    """Adiciona as colunas do Dividend Safety Score ao DataFrame da carteira."""
    notas = df.apply(calcular_dividend_safety, axis=1)
    return pd.concat([df, notas], axis=1)


# ------------------------------------------------------------------
# VALOR INTRÍNSECO (Dividend Discount Model / Modelo de Gordon)
# ------------------------------------------------------------------
# Fórmula: Valor = D1 / (r - g)
#   D1 = próximo dividendo esperado = dividendo atual × (1 + g)
#   r  = taxa de retorno exigida (o que tu esperas ganhar, ajustada ao risco)
#   g  = taxa de crescimento do dividendo a longo prazo
#
# ⚠️ Limitações importantes (por isso isto é uma ESTIMATIVA, não uma verdade):
#   - Só faz sentido para empresas que pagam dividendo de forma estável e previsível.
#     Não funciona bem para ações sem histórico de dividendos ou com cortes recentes.
#   - Assume que o dividendo cresce ao MESMO ritmo para sempre — na prática isso
#     nunca acontece exatamente assim.
#   - É extremamente sensível às assunções: pequenas mudanças em r ou g podem
#     alterar o valor calculado de forma muito significativa.
#   - Serve para teres uma referência e comparar ações entre si — não para decidir
#     sozinho se compras ou vendes.

def calcular_valor_intrinseco(row, taxa_desconto):
    dividend_rate = row.get("dividend_rate")
    g = row.get("dividend_cagr_5y")
    preco = row.get("preco")

    if pd.isna(dividend_rate) or not dividend_rate or dividend_rate <= 0 or pd.isna(g):
        return np.nan, np.nan

    # Limita g para o modelo não "explodir": tem de ser sempre menor que r,
    # e não deixamos quedas pontuais de dividendo distorcerem a estimativa a mais
    g_ajustado = min(g, taxa_desconto - 0.01)
    g_ajustado = max(g_ajustado, -0.05)

    d1 = dividend_rate * (1 + g_ajustado)
    denominador = taxa_desconto - g_ajustado
    if denominador <= 0:
        return np.nan, np.nan

    valor_intrinseco = d1 / denominador

    if pd.isna(preco) or preco <= 0 or pd.isna(valor_intrinseco):
        margem_seguranca = np.nan
    else:
        margem_seguranca = ((valor_intrinseco - preco) / valor_intrinseco) * 100

    return valor_intrinseco, margem_seguranca


def aplicar_valor_intrinseco(df, taxa_desconto):
    """Adiciona as colunas de Valor Intrínseco e Margem de Segurança ao DataFrame."""
    resultados = df.apply(lambda r: calcular_valor_intrinseco(r, taxa_desconto), axis=1)
    df = df.copy()
    df["valor_intrinseco"] = resultados.apply(lambda x: x[0])
    df["margem_seguranca"] = resultados.apply(lambda x: x[1])
    return df


# ------------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("📈 A Minha Carteira")
    st.caption("Ações de longo prazo & dividendos")
    st.divider()

    if st.button("🔄 Atualizar dados agora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    st.caption("Os dados são cacheados durante 5 minutos.")

    st.divider()
    st.markdown("**Critérios de alerta**")
    limite_minimo = st.slider("Perto do mínimo de 52 semanas (%)", 1, 30, 10)
    limite_pe = st.slider("P/E considerado atrativo (abaixo de)", 5, 40, 18)

    st.divider()
    st.markdown("**Valor Intrínseco (Dividend Discount Model)**")
    taxa_desconto_pct = st.slider(
        "Taxa de retorno exigida (r)", 6.0, 15.0, 9.0, step=0.5,
        help="O retorno anual que consideras justo exigir por investir nesta ação, dado o risco. "
             "Mais alto = valor intrínseco mais baixo (mais conservador)."
    )
    taxa_desconto = taxa_desconto_pct / 100

    st.divider()
    with st.expander("📖 Glossário para iniciantes"):
        st.markdown("""
**P/E (Price/Earnings)** — quantos anos de lucro atual precisas para "pagar" o preço da ação. Mais baixo = normalmente mais barato, mas varia muito por setor.

**P/B (Price/Book)** — preço da ação vs. o valor contabilístico da empresa. Útil para bancos e setores intensivos em ativos.

**PEG Ratio** — o P/E ajustado ao crescimento (P/E ÷ crescimento). PEG < 1 costuma ser sinal de ação barata *face ao seu crescimento*.

**ROE (Return on Equity)** — quão eficiente a empresa é a gerar lucro com o capital dos acionistas. Mais alto = melhor, em geral.

**Margem Líquida** — que % da receita vira lucro. Mede eficiência operacional.

**Payout Ratio** — % do lucro que a empresa distribui em dividendos. Baixo = sobra dinheiro para crescer e para aguentar anos maus. Exceção: REITs, que são obrigados por lei a distribuir quase tudo.

**Debt/Equity** — dívida da empresa comparada com o capital próprio. Dívida alta pode obrigar a cortar dividendos em alturas difíceis.

**CAGR do Dividendo (5 anos)** — a que ritmo médio o dividendo por ação tem crescido. Mostra se o crescimento é real, não só o yield atual.

**Anos Consecutivos de Aumento** — há quantos anos seguidos o dividendo sobe sem cortes. Empresas com 10, 25+ anos (Dividend Aristocrats) são vistas como muito fiáveis.

**Payout Ratio (FCF)** — a versão mais rigorosa do payout: usa o Free Cash Flow (dinheiro real gerado) em vez do lucro contabilístico, que pode ser "maquilhado" por amortizações e outros itens não-monetários.

**Interest Coverage Ratio** — quantas vezes o lucro operacional cobre os juros da dívida. Abaixo de 2-3x é normalmente sinal de alerta (exceto em setores estruturalmente endividados, como bancos ou utilities).

**Beta** — mede a volatilidade da ação face ao mercado. Beta 1 = mexe como o mercado; acima de 1 = mais volátil; abaixo de 1 = mais estável.

**Forward P/E** — o P/E calculado com os lucros esperados pelos analistas, em vez dos já reportados. Compara-se com o P/E normal para perceber se o mercado espera crescimento.

**ROIC (Return on Invested Capital)** — retorno gerado sobre TODO o capital do negócio (dívida + capital próprio), não só o capital próprio como o ROE. Mais difícil de "inflacionar" com dívida, é visto como um sinal mais fiável da qualidade real de um negócio.

**Valor Intrínseco (Dividend Discount Model)** — estimativa de quanto uma ação "deveria" valer, com base nos dividendos esperados e numa taxa de retorno exigida. É uma referência, não uma verdade absoluta — só funciona bem para empresas com dividendo estável, e é sensível às assunções usadas.

**Quant Rating** — nota combinada (Strong Buy / Buy / Hold) juntando Valuation + Growth + Profitability.

**Dividend Safety** — nota (A-D) que diz se o dividendo atual parece sustentável a longo prazo, combinando payout, dívida e histórico de crescimento.
        """)

# ------------------------------------------------------------------
# CARREGAR DADOS
# ------------------------------------------------------------------
with st.spinner("A carregar cotações..."):
    df = carregar_carteira()
    df = aplicar_factor_grades(df)
    df = aplicar_dividend_safety(df)
    df = aplicar_valor_intrinseco(df, taxa_desconto)

st.title("📊 Painel Diário da Carteira")

# ------------------------------------------------------------------
# MÉTRICAS GERAIS
# ------------------------------------------------------------------
peso_total = df["peso"].sum()
variacao_media_ponderada = np.nansum(df["variacao_pct"] * df["peso"]) / peso_total if peso_total else np.nan
yield_medio_ponderado = np.nansum(df["dividend_yield"].fillna(0) * df["peso"]) / peso_total if peso_total else np.nan
n_alertas_min = (df["dist_do_minimo"] <= limite_minimo).sum()
n_alertas_pe = ((df["pe_ratio"] < limite_pe) & (df["pe_ratio"] > 0)).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Peso total definido", f"{peso_total}%")
c2.metric("Variação diária ponderada", formata_pct(variacao_media_ponderada),
          delta=formata_pct(variacao_media_ponderada))
c3.metric("Dividend Yield médio ponderado", formata_pct(yield_medio_ponderado))
c4.metric("Ativos em alerta", int(n_alertas_min + n_alertas_pe))

st.divider()

# ------------------------------------------------------------------
# TABS
# ------------------------------------------------------------------
tab_resumo, tab_alertas, tab_alocacao, tab_ratings, tab_dividendos, tab_intrinseco, tab_reforco, tab_detalhe = st.tabs(
    ["📋 Resumo", "🚨 Alertas", "🥧 Alocação", "🏆 Quant Ratings", "💰 Dividend Safety",
     "🧮 Valor Intrínseco", "💎 Oportunidades de Reforço", "🔍 Detalhe por Ativo"]
)

# ---------------- TAB RESUMO ----------------
with tab_resumo:
    st.subheader("Tabela Resumo")

    tabela = df.copy()
    tabela_view = pd.DataFrame({
        "Ticker": tabela["ticker"],
        "Nome": tabela["nome_completo"],
        "Peso": tabela["peso"].map(lambda x: f"{x}%"),
        "Preço": tabela.apply(lambda r: f"{r['preco']:.2f} {r['moeda']}" if pd.notna(r["preco"]) else "N/D", axis=1),
        "Var. Dia": tabela["variacao_pct"].map(formata_pct),
        "P/E": tabela["pe_ratio"].map(lambda x: f"{x:.1f}" if pd.notna(x) and x else "N/D"),
        "Div. Yield": tabela["dividend_yield"].map(formata_pct),
        "Cap. Bolsista": tabela["market_cap"].map(formata_grande),
        "Dist. Mín 52s": tabela["dist_do_minimo"].map(formata_pct),
        "Rating": tabela["quant_rating"],
        "Div. Safety": tabela["grade_dividend_safety"],
    })

    def cor_variacao(val):
        try:
            v = float(str(val).replace("%", "").replace("N/D", "nan"))
        except Exception:
            return ""
        if np.isnan(v):
            return ""
        cor = "#00c853" if v >= 0 else "#ff5252"
        return f"color: {cor}; font-weight: 600;"

    def cor_rating(val):
        cores = {"Strong Buy": "#00c853", "Buy": "#7cd992", "Hold": "#ffb300"}
        cor = cores.get(val, "")
        return f"color: {cor}; font-weight: 600;" if cor else ""

    def cor_nota_letra(val):
        cores = {"A": "#00c853", "B": "#7cd992", "C": "#ffb300", "D": "#ff5252"}
        cor = cores.get(val, "")
        return f"color: {cor}; font-weight: 600;" if cor else ""

    styled = (
        tabela_view.style
        .map(cor_variacao, subset=["Var. Dia"])
        .map(cor_rating, subset=["Rating"])
        .map(cor_nota_letra, subset=["Div. Safety"])
    )
    st.dataframe(styled, use_container_width=True, height=600, hide_index=True)

# ---------------- TAB ALERTAS ----------------
with tab_alertas:
    st.subheader("Ativos com Sinais de Interesse")
    st.caption("Ações perto de mínimos de 52 semanas ou com múltiplos (P/E) atrativos.")

    algum_alerta = False
    for _, row in df.sort_values("dist_do_minimo").iterrows():
        perto_do_minimo = pd.notna(row["dist_do_minimo"]) and row["dist_do_minimo"] <= limite_minimo
        pe_atrativo = pd.notna(row["pe_ratio"]) and 0 < row["pe_ratio"] < limite_pe

        if perto_do_minimo or pe_atrativo:
            algum_alerta = True
            motivos = []
            if perto_do_minimo:
                motivos.append(f"a apenas {formata_pct(row['dist_do_minimo'])} do mínimo de 52 semanas")
            if pe_atrativo:
                motivos.append(f"P/E atrativo de {row['pe_ratio']:.1f}")

            classe = "alert-card-green" if perto_do_minimo and pe_atrativo else "alert-card-yellow"
            st.markdown(f"""
            <div class="{classe}">
                <b>{row['nome']} ({row['ticker']})</b> — {' e '.join(motivos)}.<br>
                Preço atual: {row['preco']:.2f} {row['moeda']} | Peso na carteira: {row['peso']}%
            </div>
            """, unsafe_allow_html=True)

    if not algum_alerta:
        st.info("Nenhum ativo cumpre atualmente os critérios de alerta definidos na barra lateral.")

    st.divider()
    st.subheader("Maiores variações do dia")
    col_sobem, col_descem = st.columns(2)
    top_sobem = df.sort_values("variacao_pct", ascending=False).head(3)
    top_descem = df.sort_values("variacao_pct", ascending=True).head(3)

    with col_sobem:
        st.markdown("**📈 Em alta**")
        for _, r in top_sobem.iterrows():
            st.markdown(f"""<div class="alert-card-green">{r['ticker']} — {formata_pct(r['variacao_pct'])}</div>""",
                        unsafe_allow_html=True)
    with col_descem:
        st.markdown("**📉 Em baixa**")
        for _, r in top_descem.iterrows():
            st.markdown(f"""<div class="alert-card-red">{r['ticker']} — {formata_pct(r['variacao_pct'])}</div>""",
                        unsafe_allow_html=True)

# ---------------- TAB ALOCAÇÃO ----------------
with tab_alocacao:
    st.subheader("Distribuição da Carteira por Peso Definido")
    fig = px.pie(
        df, names="ticker", values="peso", hole=0.45,
        color_discrete_sequence=px.colors.sequential.Tealgrn,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        legend_title_text="Ticker",
    )
    st.plotly_chart(fig, use_container_width=True)

    fig_bar = px.bar(
        df.sort_values("peso"), x="peso", y="ticker", orientation="h",
        text="peso", color="peso", color_continuous_scale="Teal",
    )
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        showlegend=False,
        xaxis_title="Peso (%)",
        yaxis_title="",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ---------------- TAB QUANT RATINGS ----------------
with tab_ratings:
    st.subheader("Factor Grades & Quant Rating")
    st.caption(
        "Notas de A (melhor) a D (pior), calculadas **em relação à média típica do setor "
        "de cada ativo** — critério usado por casas de research profissionais, já que um "
        "P/E de 25 é caro para um banco mas normal para uma tech. "
        "Valuation considera P/E, P/B e PEG; Growth considera crescimento de receita e "
        "resultados; Profitability considera ROE e margem líquida. "
        "O Quant Rating combina as três notas."
    )

    cores_nota = {"A": "#00c853", "B": "#7cd992", "C": "#ffb300", "D": "#ff5252"}
    cores_rating = {"Strong Buy": "#00c853", "Buy": "#7cd992", "Hold": "#ffb300"}

    n_cols = 4
    linhas_ordenadas = df.sort_values("score_quant", ascending=False).reset_index(drop=True)
    for i in range(0, len(linhas_ordenadas), n_cols):
        cols = st.columns(n_cols)
        for col, (_, row) in zip(cols, linhas_ordenadas.iloc[i:i + n_cols].iterrows()):
            with col:
                cor_r = cores_rating.get(row["quant_rating"], "#888")
                st.markdown(f"""
                <div class="metric-card">
                    <b>{row['ticker']}</b> — {row['nome']}<br>
                    <span style="color:{cor_r}; font-weight:700;">{row['quant_rating']}</span><br><br>
                    Valuation: <span style="color:{cores_nota.get(row['grade_valuation'])}; font-weight:700;">{row['grade_valuation']}</span> &nbsp;
                    Growth: <span style="color:{cores_nota.get(row['grade_growth'])}; font-weight:700;">{row['grade_growth']}</span> &nbsp;
                    Profitability: <span style="color:{cores_nota.get(row['grade_profitability'])}; font-weight:700;">{row['grade_profitability']}</span>
                </div>
                """, unsafe_allow_html=True)

# ---------------- TAB DIVIDEND SAFETY ----------------
with tab_dividendos:
    st.subheader("Dividend Safety Score")
    st.caption(
        "Diz-te se o dividendo de cada ação parece sustentável a longo prazo — não basta "
        "o yield ser alto, tem de haver lucro e caixa para o sustentar. Combina Payout Ratio "
        "(lucro e FCF), Debt/Equity, Cobertura de Juros, anos consecutivos de aumento e o "
        "ritmo real de crescimento do dividendo."
    )

    with st.expander("❓ Como interpretar esta nota (clica para abrir)"):
        st.markdown("""
- **A — Muito Seguro**: payout baixo para o setor, dívida controlada, histórico longo de aumentos.
- **B — Saudável**: fundamentos sólidos, sem sinais de alarme.
- **C — Moderado**: pelo menos um indicador no limite (ex: payout já alto, ou dívida elevada).
- **D — Atenção**: vários sinais de alerta em simultâneo — vale a pena investigar antes de reforçar.

Nota: para REITs e Utilities, um payout mais alto é normal (faz parte do modelo de negócio) e já está refletido nas bandas usadas.
        """)

    cores_nota = {"A": "#00c853", "B": "#7cd992", "C": "#ffb300", "D": "#ff5252"}

    dividendos_ordenados = df.sort_values("score_dividend_safety", ascending=False).reset_index(drop=True)
    n_cols = 3
    for i in range(0, len(dividendos_ordenados), n_cols):
        cols = st.columns(n_cols)
        for col, (_, row) in zip(cols, dividendos_ordenados.iloc[i:i + n_cols].iterrows()):
            with col:
                cor_n = cores_nota.get(row["grade_dividend_safety"], "#888")
                payout_txt = formata_pct(row["payout_ratio"], 0)
                fcf_payout_txt = formata_pct(row["fcf_payout_ratio"], 0) if pd.notna(row["fcf_payout_ratio"]) else "N/D"
                debt_txt = f"{row['debt_to_equity']:.0f}%" if pd.notna(row["debt_to_equity"]) else "N/D"
                cobertura_txt = f"{row['interest_coverage']:.1f}x" if pd.notna(row["interest_coverage"]) else "N/D"
                anos_txt = f"{int(row['anos_consecutivos_crescimento'])} anos" if pd.notna(row["anos_consecutivos_crescimento"]) else "N/D"
                cagr_txt = formata_pct(row["dividend_cagr_5y"] * 100, 1) if pd.notna(row["dividend_cagr_5y"]) else "N/D"
                yield_5y_txt = formata_pct(row["yield_medio_5anos"], 2)

                st.markdown(f"""
                <div class="metric-card">
                    <b>{row['ticker']}</b> — {row['nome']}<br>
                    <span style="color:{cor_n}; font-weight:700; font-size:16px;">
                        {row['grade_dividend_safety']} · {row['dividend_safety_label']}
                    </span><br><br>
                    Payout Ratio (lucro): <b>{payout_txt}</b><br>
                    Payout Ratio (FCF): <b>{fcf_payout_txt}</b><br>
                    Debt/Equity: <b>{debt_txt}</b><br>
                    Cobertura de Juros: <b>{cobertura_txt}</b><br>
                    Anos a aumentar: <b>{anos_txt}</b><br>
                    CAGR Dividendo (5a): <b>{cagr_txt}</b><br>
                    Yield atual vs. média 5a: <b>{formata_pct(row['dividend_yield'])}</b> vs <b>{yield_5y_txt}</b>
                </div>
                """, unsafe_allow_html=True)

    st.divider()
    st.caption(
        "💡 Dica para novatos: um yield atual bem acima da média de 5 anos pode ser uma boa "
        "oportunidade (ação descontada) — mas confirma sempre com o Payout Ratio e o Debt/Equity, "
        "porque também pode ser sinal de que o mercado antecipa problemas."
    )

# ---------------- TAB VALOR INTRÍNSECO ----------------
with tab_intrinseco:
    st.subheader("Valor Intrínseco — Dividend Discount Model")
    st.caption(
        f"Estimativa de quanto cada ação 'deveria' valer, com base nos dividendos esperados "
        f"e numa taxa de retorno exigida de **{taxa_desconto_pct:.1f}%** (ajustável na barra lateral)."
    )

    with st.expander("❓ Como funciona e principais limitações (lê antes de confiar nos números)"):
        st.markdown("""
**Fórmula usada (Modelo de Gordon / Dividend Discount Model):**

`Valor Intrínseco = Próximo Dividendo ÷ (Taxa de Retorno Exigida − Taxa de Crescimento do Dividendo)`

**⚠️ Limitações importantes — isto é uma estimativa, não uma verdade:**
- Só faz sentido para empresas com **histórico de dividendos estável**. Ações sem dividendo, ou com cortes recentes, aparecem como "N/D" — o modelo simplesmente não se aplica a elas.
- Assume que o dividendo cresce sempre ao mesmo ritmo, para sempre — o que nunca é exatamente verdade.
- É **muito sensível** às assunções: mudar a taxa de retorno exigida em 1-2% pode alterar bastante o valor calculado. Usa isto para comparar ações entre si, não como um preço-alvo exato.
- A taxa de crescimento usada é a **CAGR histórica dos últimos 5 anos** — não há garantia de que o futuro repita o passado.

**Margem de Segurança** = quanto a ação está abaixo (positivo) ou acima (negativo) do valor intrínseco estimado. Quanto maior a margem positiva, maior o "desconto" teórico.
        """)

    intrinseco_df = df.copy()
    intrinseco_df = intrinseco_df.dropna(subset=["valor_intrinseco"])

    if intrinseco_df.empty:
        st.info(
            "Nenhum ativo tem dados suficientes (histórico de dividendos estável) para este modelo "
            "com a taxa de retorno atual. Experimenta baixar a taxa de retorno exigida na barra lateral."
        )
    else:
        intrinseco_df = intrinseco_df.sort_values("margem_seguranca", ascending=False)

        tabela_intrinseco = pd.DataFrame({
            "Ticker": intrinseco_df["ticker"],
            "Nome": intrinseco_df["nome"],
            "Preço Atual": intrinseco_df.apply(
                lambda r: f"{r['preco']:.2f} {r['moeda']}" if pd.notna(r["preco"]) else "N/D", axis=1),
            "Valor Intrínseco": intrinseco_df["valor_intrinseco"].map(lambda x: f"{x:.2f}"),
            "Margem de Segurança": intrinseco_df["margem_seguranca"].map(formata_pct),
        })

        def cor_margem(val):
            try:
                v = float(str(val).replace("%", "").replace("N/D", "nan"))
            except Exception:
                return ""
            if np.isnan(v):
                return ""
            cor = "#00c853" if v >= 0 else "#ff5252"
            return f"color: {cor}; font-weight: 600;"

        styled_intrinseco = tabela_intrinseco.style.map(cor_margem, subset=["Margem de Segurança"])
        st.dataframe(styled_intrinseco, use_container_width=True, height=500, hide_index=True)

        n_sem_dados = len(df) - len(intrinseco_df)
        if n_sem_dados > 0:
            st.caption(
                f"ℹ️ {n_sem_dados} ativo(s) não aparecem na tabela por não terem histórico de dividendos "
                "estável suficiente para aplicar este modelo (ex: ações sem dividendo ou com crescimento ≥ taxa de retorno exigida)."
            )

    st.caption(
        "💡 Dica para novatos: usa este modelo em conjunto com o Quant Rating e o Dividend Safety — "
        "uma margem de segurança positiva não vale muito se o dividendo estiver em risco (nota D)."
    )

# ---------------- TAB OPORTUNIDADES DE REFORÇO ----------------
with tab_reforco:
    st.subheader("Oportunidades de Reforço")
    st.caption(
        "Ativos ordenados do mais para o menos atrativo, combinando o Quant Rating "
        "com a proximidade ao mínimo de 52 semanas."
    )

    reforco = df.copy()
    # Score de oportunidade: score_quant (0-4) + bónus por estar perto do mínimo de 52 semanas
    reforco["bonus_minimo"] = reforco["dist_do_minimo"].apply(
        lambda x: max(0, (20 - x) / 20) if pd.notna(x) and x <= 20 else 0
    )
    reforco["score_oportunidade"] = reforco["score_quant"] + reforco["bonus_minimo"]
    reforco = reforco.sort_values("score_oportunidade", ascending=False)

    tabela_reforco = pd.DataFrame({
        "Ticker": reforco["ticker"],
        "Nome": reforco["nome"],
        "Rating": reforco["quant_rating"],
        "Valuation": reforco["grade_valuation"],
        "Growth": reforco["grade_growth"],
        "Profitability": reforco["grade_profitability"],
        "Preço": reforco.apply(lambda r: f"{r['preco']:.2f} {r['moeda']}" if pd.notna(r["preco"]) else "N/D", axis=1),
        "Dist. Mín 52s": reforco["dist_do_minimo"].map(formata_pct),
        "Peso Atual": reforco["peso"].map(lambda x: f"{x}%"),
    })

    def cor_rating_reforco(val):
        cores = {"Strong Buy": "#00c853", "Buy": "#7cd992", "Hold": "#ffb300"}
        cor = cores.get(val, "")
        return f"color: {cor}; font-weight: 600;" if cor else ""

    def cor_nota_reforco(val):
        cores = {"A": "#00c853", "B": "#7cd992", "C": "#ffb300", "D": "#ff5252"}
        cor = cores.get(val, "")
        return f"color: {cor}; font-weight: 600;" if cor else ""

    styled_reforco = (
        tabela_reforco.style
        .map(cor_rating_reforco, subset=["Rating"])
        .map(cor_nota_reforco, subset=["Valuation", "Growth", "Profitability"])
    )
    st.dataframe(styled_reforco, use_container_width=True, height=600, hide_index=True)

    top3 = reforco.head(3)
    if not top3.empty:
        st.divider()
        st.markdown("**🥇 Top 3 para reforçar agora**")
        for _, r in top3.iterrows():
            st.markdown(f"""
            <div class="alert-card-green">
                <b>{r['ticker']} — {r['nome']}</b> ({r['quant_rating']})<br>
                Valuation {r['grade_valuation']} · Growth {r['grade_growth']} · Profitability {r['grade_profitability']}
                {' · a ' + formata_pct(r['dist_do_minimo']) + ' do mínimo de 52 semanas' if pd.notna(r['dist_do_minimo']) and r['dist_do_minimo'] <= 20 else ''}
            </div>
            """, unsafe_allow_html=True)

# ---------------- TAB DETALHE ----------------
with tab_detalhe:
    ticker_escolhido = st.selectbox(
        "Escolhe um ativo", options=df["ticker"],
        format_func=lambda tk: f"{tk} — {df[df['ticker']==tk]['nome'].values[0]}",
    )
    linha = df[df["ticker"] == ticker_escolhido].iloc[0]

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Preço", f"{linha['preco']:.2f} {linha['moeda']}" if pd.notna(linha['preco']) else "N/D",
                 delta=formata_pct(linha["variacao_pct"]))
    col_b.metric("P/E Ratio", f"{linha['pe_ratio']:.1f}" if pd.notna(linha["pe_ratio"]) else "N/D",
                 help="Quantos anos de lucro atual 'pagam' o preço da ação. Compara-se sempre com o setor, nunca isolado.")
    col_c.metric("Dividend Yield", formata_pct(linha["dividend_yield"]),
                 help="Dividendo anual dividido pelo preço atual da ação.")
    col_d.metric("Cap. Bolsista", formata_grande(linha["market_cap"]),
                 help="Valor total de mercado da empresa (preço da ação × nº de ações).")

    col_e, col_f, col_e2, col_f2 = st.columns(4)
    col_e.metric("Mínimo 52 semanas", f"{linha['low_52']:.2f}" if pd.notna(linha["low_52"]) else "N/D",
                 delta=formata_pct(linha["dist_do_minimo"]) + " acima do mínimo")
    col_f.metric("Máximo 52 semanas", f"{linha['high_52']:.2f}" if pd.notna(linha["high_52"]) else "N/D",
                 delta="-" + formata_pct(linha["dist_do_maximo"]) + " abaixo do máximo")
    col_e2.metric("Forward P/E", f"{linha['forward_pe']:.1f}" if pd.notna(linha["forward_pe"]) else "N/D",
                  help="P/E calculado com os lucros ESPERADOS (analistas) em vez dos lucros já reportados. Se for mais baixo que o P/E normal, o mercado espera que os lucros cresçam.")
    col_f2.metric("Beta", f"{linha['beta']:.2f}" if pd.notna(linha["beta"]) else "N/D",
                  help="Mede a volatilidade da ação face ao mercado (S&P 500). Beta 1 = mexe como o mercado; >1 = mais volátil; <1 = mais estável. Útil para perceberes o nível de risco/oscilação a esperar.")

    st.divider()
    st.subheader("Factor Grades & Quant Rating")
    cores_nota = {"A": "#00c853", "B": "#7cd992", "C": "#ffb300", "D": "#ff5252"}
    cores_rating = {"Strong Buy": "#00c853", "Buy": "#7cd992", "Hold": "#ffb300"}
    cor_r = cores_rating.get(linha["quant_rating"], "#888")
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:{cor_r}; font-weight:700; font-size:18px;">{linha['quant_rating']}</span><br><br>
        Valuation: <span style="color:{cores_nota.get(linha['grade_valuation'])}; font-weight:700;">{linha['grade_valuation']}</span> &nbsp;&nbsp;
        Growth: <span style="color:{cores_nota.get(linha['grade_growth'])}; font-weight:700;">{linha['grade_growth']}</span> &nbsp;&nbsp;
        Profitability: <span style="color:{cores_nota.get(linha['grade_profitability'])}; font-weight:700;">{linha['grade_profitability']}</span>
    </div>
    """, unsafe_allow_html=True)
    st.metric("ROIC", formata_pct(linha["roic"], 1) if pd.notna(linha["roic"]) else "N/D",
              help="Retorno sobre TODO o capital investido (dívida + capital próprio), não só o capital próprio como no ROE. Mais difícil de 'inflacionar' com dívida — mede a qualidade real do negócio.")

    st.divider()
    st.subheader("🧮 Valor Intrínseco")
    if pd.notna(linha["valor_intrinseco"]):
        cor_margem_card = "#00c853" if linha["margem_seguranca"] >= 0 else "#ff5252"
        st.markdown(f"""
        <div class="metric-card">
            Valor Intrínseco estimado: <b>{linha['valor_intrinseco']:.2f} {linha['moeda']}</b> (vs. preço atual {linha['preco']:.2f} {linha['moeda']})<br>
            Margem de Segurança: <span style="color:{cor_margem_card}; font-weight:700;">{formata_pct(linha['margem_seguranca'])}</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Calculado com taxa de retorno exigida de {taxa_desconto_pct:.1f}% (Dividend Discount Model — ver aba 🧮 Valor Intrínseco para detalhes e limitações).")
    else:
        st.info("Não há histórico de dividendos estável suficiente para aplicar este modelo a este ativo.")

    st.divider()
    st.subheader("💰 Dividend Safety")
    cor_ds = cores_nota.get(linha["grade_dividend_safety"], "#888")
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:{cor_ds}; font-weight:700; font-size:18px;">
            {linha['grade_dividend_safety']} · {linha['dividend_safety_label']}
        </span>
    </div>
    """, unsafe_allow_html=True)

    col_k, col_l = st.columns(2)
    col_k.metric("Payout Ratio (FCF)", formata_pct(linha["fcf_payout_ratio"], 0) if pd.notna(linha["fcf_payout_ratio"]) else "N/D",
                 help="Dividendos pagos vs. Free Cash Flow (dinheiro real gerado). Mais rigoroso que o payout baseado no lucro contabilístico, porque não é afetado por amortizações ou itens não-monetários.")
    col_l.metric("Cobertura de Juros", f"{linha['interest_coverage']:.1f}x" if pd.notna(linha["interest_coverage"]) else "N/D",
                 help="Quantas vezes o lucro operacional (EBIT) cobre a despesa com juros da dívida. Quanto mais alto, mais folga a empresa tem para pagar a dívida sem pôr o dividendo em risco.")

    col_g, col_h, col_i, col_j = st.columns(4)
    col_g.metric("Payout Ratio", formata_pct(linha["payout_ratio"], 0),
                 help="% do lucro distribuído em dividendos. Mais baixo = mais 'almofada' para aguentar anos maus sem cortar o dividendo (exceto REITs/Utilities, que são naturalmente mais altos).")
    col_h.metric("Debt/Equity", f"{linha['debt_to_equity']:.0f}%" if pd.notna(linha["debt_to_equity"]) else "N/D",
                 help="Dívida da empresa comparada com o capital próprio. Dívida elevada pode obrigar a cortar dividendos para pagar credores primeiro.")
    col_i.metric("Anos a Aumentar", f"{int(linha['anos_consecutivos_crescimento'])}" if pd.notna(linha["anos_consecutivos_crescimento"]) else "N/D",
                 help="Anos consecutivos em que a empresa aumentou o dividendo, sem cortar nem congelar.")
    col_j.metric("CAGR Dividendo (5a)", formata_pct(linha["dividend_cagr_5y"] * 100, 1) if pd.notna(linha["dividend_cagr_5y"]) else "N/D",
                 help="Taxa média anual a que o dividendo por ação cresceu nos últimos ~5 anos.")

    st.caption(
        f"Yield atual: **{formata_pct(linha['dividend_yield'])}** · "
        f"Yield médio dos últimos 5 anos: **{formata_pct(linha['yield_medio_5anos'])}**  \n"
        "Se o yield atual estiver bem acima da média histórica, pode ser sinal de ação descontada — "
        "mas confirma sempre com o Payout Ratio antes de concluir isso."
    )

    st.divider()
    st.subheader(f"Histórico de Preço — {ticker_escolhido} (1 ano)")
    try:
        hist = yf.Ticker(ticker_escolhido).history(period="1y")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=hist.index, y=hist["Close"], mode="lines",
            line=dict(color="#00c853", width=2), fill="tozeroy",
            fillcolor="rgba(0,200,83,0.08)",
        ))
        fig_line.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="", yaxis_title="Preço",
        )
        st.plotly_chart(fig_line, use_container_width=True)
    except Exception:
        st.warning("Não foi possível carregar o histórico deste ativo.")

st.divider()
st.caption("⚠️ Esta aplicação é apenas informativa e não constitui aconselhamento financeiro. "
           "Os dados são fornecidos pelo Yahoo Finance através da biblioteca yfinance e podem ter atrasos.")
