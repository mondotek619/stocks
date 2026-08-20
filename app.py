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
    {"nome": "Broadcom",         "ticker": "AVGO",    "peso": 5},
    {"nome": "Alphabet",         "ticker": "GOOGL",   "peso": 10},
    {"nome": "ASML Holding",     "ticker": "ASML",    "peso": 10},
    {"nome": "JPMorgan Chase",   "ticker": "JPM",     "peso": 10},
    {"nome": "Mastercard",       "ticker": "MA",      "peso": 7},
    {"nome": "Walt Disney",      "ticker": "DIS",     "peso": 5},
    {"nome": "PepsiCo",          "ticker": "PEP",     "peso": 6},
    {"nome": "Realty Income",    "ticker": "O",       "peso": 6},
    {"nome": "Ecolab",           "ticker": "ECL",     "peso": 6},
    {"nome": "Zoetis",           "ticker": "ZTS",     "peso": 5},
    {"nome": "Novo Nordisk",     "ticker": "NVO",     "peso": 5},
    {"nome": "UnitedHealth",     "ticker": "UNH",     "peso": 5},
    {"nome": "Munich Re",        "ticker": "MUV2.DE", "peso": 5},
    {"nome": "Cameco Corp",      "ticker": "CCJ",     "peso": 5},
    {"nome": "Vistra Corp",      "ticker": "VST",     "peso": 5},
    {"nome": "Caterpillar",      "ticker": "CAT",     "peso": 5},
]

TICKERS = [a["ticker"] for a in PORTFOLIO]

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
            })
        linhas.append(linha)
    return pd.DataFrame(linhas)


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
tab_resumo, tab_alertas, tab_alocacao, tab_detalhe = st.tabs(
    ["📋 Resumo", "🚨 Alertas", "🥧 Alocação", "🔍 Detalhe por Ativo"]
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

    styled = tabela_view.style.applymap(cor_variacao, subset=["Var. Dia"])
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
