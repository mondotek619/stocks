"""
Dashboard de Carteira - Ações de Longo Prazo e Dividendos
Streamlit + yfinance
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
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
    {"nome": "Broadcom",         "ticker": "AVGO",    "peso": 5,  "setor": "Tecnologia"},
    {"nome": "Alphabet",         "ticker": "GOOGL",   "peso": 10, "setor": "Tecnologia"},
    {"nome": "ASML Holding",     "ticker": "ASML",    "peso": 10, "setor": "Tecnologia"},
    {"nome": "JPMorgan Chase",   "ticker": "JPM",     "peso": 10, "setor": "Financeiro"},
    {"nome": "Mastercard",       "ticker": "MA",      "peso": 7,  "setor": "Financeiro"},
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
        "growth": [5, 12, 20], "roe": [15, 22, 30], "margin": [12, 20, 28],
    },
    "Financeiro": {
        "pe": [9, 12, 16], "pb": [1.0, 1.8, 2.5],
        "growth": [2, 6, 10], "roe": [8, 12, 16], "margin": [15, 22, 30],
    },
    "Financeiro (Seguros)": {
        "pe": [8, 11, 14], "pb": [0.9, 1.5, 2.2],
        "growth": [2, 5, 9], "roe": [7, 11, 15], "margin": [8, 14, 20],
    },
    "Consumo Discricionário": {
        "pe": [15, 22, 30], "pb": [2.5, 4.5, 7],
        "growth": [3, 8, 14], "roe": [10, 16, 24], "margin": [4, 8, 14],
    },
    "Consumo Básico": {
        "pe": [16, 21, 26], "pb": [3, 6, 9],
        "growth": [0, 4, 8], "roe": [15, 22, 30], "margin": [6, 11, 16],
    },
    "Imobiliário (REIT)": {
        "pe": [14, 19, 25], "pb": [1.2, 1.8, 2.5],
        "growth": [-2, 3, 7], "roe": [4, 7, 11], "margin": [15, 25, 35],
    },
    "Industrial": {
        "pe": [14, 19, 24], "pb": [2.5, 4.5, 7],
        "growth": [0, 6, 12], "roe": [10, 16, 22], "margin": [5, 10, 15],
    },
    "Saúde": {
        "pe": [14, 20, 27], "pb": [3, 5.5, 8],
        "growth": [2, 8, 15], "roe": [10, 16, 24], "margin": [6, 12, 18],
    },
    "Energia/Materiais": {
        "pe": [7, 11, 16], "pb": [1.2, 2.2, 3.5],
        "growth": [-5, 3, 10], "roe": [5, 10, 16], "margin": [5, 12, 20],
    },
    "Utilities": {
        "pe": [14, 18, 23], "pb": [1.5, 2.2, 3],
        "growth": [-1, 2, 5], "roe": [7, 10, 14], "margin": [6, 10, 15],
    },
    # Aplicado quando o setor não está mapeado acima
    "_default": {
        "pe": [15, 20, 30], "pb": [2, 4, 6],
        "growth": [0, 8, 15], "roe": [5, 12, 20], "margin": [5, 12, 20],
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


@st.cache_data(ttl=300, show_spinner=False)
def obter_dados(ticker):
    """Vai buscar dados fundamentais e de mercado a um ticker via yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        hist = t.history(period="1y")
        if hist.empty:
            return None

        preco_atual = info.get("currentPrice") or info.get("regularMarketPrice") or hist["Close"].iloc[-1]
        fecho_anterior = info.get("previousClose") or (hist["Close"].iloc[-2] if len(hist) > 1 else preco_atual)
        variacao_pct = ((preco_atual - fecho_anterior) / fecho_anterior) * 100 if fecho_anterior else np.nan

        pe_ratio = info.get("trailingPE", np.nan)

        div_yield_raw = info.get("dividendYield", None)
        if div_yield_raw is None:
            dividend_yield = np.nan
        else:
            # yfinance por vezes devolve fração (0.03) e por vezes já em percentagem (3.0)
            dividend_yield = div_yield_raw * 100 if div_yield_raw < 1 else div_yield_raw

        market_cap = info.get("marketCap", np.nan)

        low_52 = info.get("fiftyTwoWeekLow", hist["Low"].min())
        high_52 = info.get("fiftyTwoWeekHigh", hist["High"].max())

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
        }
    except Exception as e:
        return {"erro": str(e)}


@st.cache_data(ttl=300, show_spinner=False)
def carregar_carteira():
    linhas = []
    for ativo in PORTFOLIO:
        dados = obter_dados(ativo["ticker"])
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
                "peg_ratio": np.nan,
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

    # ---- Profitability: ROE e margem líquida (valores em %), vs. banda do setor ----
    roe_pct = row.get("roe") * 100 if pd.notna(row.get("roe")) else np.nan
    margem_pct = row.get("profit_margin") * 100 if pd.notna(row.get("profit_margin")) else np.nan
    score_profitability = np.mean([
        _pontos_metrica(roe_pct, bandas["roe"], maior_melhor=True),
        _pontos_metrica(margem_pct, bandas["margin"], maior_melhor=True),
    ])

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

# ------------------------------------------------------------------
# CARREGAR DADOS
# ------------------------------------------------------------------
with st.spinner("A carregar cotações..."):
    df = carregar_carteira()
    df = aplicar_factor_grades(df)

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
tab_resumo, tab_alertas, tab_alocacao, tab_ratings, tab_reforco, tab_detalhe = st.tabs(
    ["📋 Resumo", "🚨 Alertas", "🥧 Alocação", "🏆 Quant Ratings", "💎 Oportunidades de Reforço", "🔍 Detalhe por Ativo"]
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

    styled = tabela_view.style.map(cor_variacao, subset=["Var. Dia"]).map(cor_rating, subset=["Rating"])
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
    col_b.metric("P/E Ratio", f"{linha['pe_ratio']:.1f}" if pd.notna(linha["pe_ratio"]) else "N/D")
    col_c.metric("Dividend Yield", formata_pct(linha["dividend_yield"]))
    col_d.metric("Cap. Bolsista", formata_grande(linha["market_cap"]))

    col_e, col_f = st.columns(2)
    col_e.metric("Mínimo 52 semanas", f"{linha['low_52']:.2f}" if pd.notna(linha["low_52"]) else "N/D",
                 delta=formata_pct(linha["dist_do_minimo"]) + " acima do mínimo")
    col_f.metric("Máximo 52 semanas", f"{linha['high_52']:.2f}" if pd.notna(linha["high_52"]) else "N/D",
                 delta="-" + formata_pct(linha["dist_do_maximo"]) + " abaixo do máximo")

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
 
