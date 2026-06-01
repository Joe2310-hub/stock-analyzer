import os
import math
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

from data import get_stock_data
from indicators import calculate_indicators
from analysis import get_recommendation
from scoring import long_term_score, short_term_score, decision_logic
from sentiment import analyze_news_sentiment

load_dotenv()

# Streamlit Cloud: Keys aus st.secrets laden falls nicht in Umgebung
if not os.getenv("ANTHROPIC_API_KEY"):
    try:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
if not os.getenv("FMP_API_KEY"):
    try:
        os.environ["FMP_API_KEY"] = st.secrets["FMP_API_KEY"]
    except Exception:
        pass

st.set_page_config(
    page_title="Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: 600; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


def fmt_money(val):
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.0f}B"
    return f"${val/1e6:.0f}M"


def delta_color(val, good_above=0):
    if val is None:
        return "off"
    return "normal" if val > good_above else "inverse"


def safe_num(val):
    """Return val as float only if it's a finite real number, else None."""
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fmt_num(val, fmt=".1f") -> str:
    v = safe_num(val)
    return f"{v:{fmt}}" if v is not None else "N/A"


# ── Header ────────────────────────────────────────────────────────────────────
st.title("📈 Stock Analyzer")
st.caption("Analyse nach Buffett & Lynch Methodik")

col_ticker, col_mode, col_btn = st.columns([2, 2, 1])
with col_ticker:
    ticker_input = st.text_input(
        "Ticker", placeholder="z.B. AAPL, MSFT, NVDA", label_visibility="collapsed"
    ).upper().strip()
with col_mode:
    mode = st.selectbox(
        "Modus",
        ["Beides (Long + Short)", "Long-Term (Fundamental)", "Short-Term (Technisch)"],
        label_visibility="collapsed",
    )
with col_btn:
    analyze = st.button("Analysieren 🔍", use_container_width=True, type="primary")

if not os.getenv("ANTHROPIC_API_KEY"):
    st.warning("⚠️  ANTHROPIC_API_KEY fehlt — KI-Tab wird nicht funktionieren. Kopiere `.env.example` → `.env` und trag deinen Key ein.")

# ── Analysis ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def cached_stock_data(ticker):
    return get_stock_data(ticker)

if ticker_input and analyze:
    with st.spinner(f"Lade Daten für **{ticker_input}** …"):
        try:
            data = cached_stock_data(ticker_input)
            fund = data["fundamentals"]
            hist = data["history_1y"]
            news = data["news"]
            tech = calculate_indicators(hist)
            lt = long_term_score(fund, tech)
            st_sc = short_term_score(fund, tech)
            decision = decision_logic(lt, st_sc, fund, tech)
            sent = analyze_news_sentiment(news, ticker_input) if news else {}
        except Exception as e:
            st.error(str(e))
            st.stop()

    # ── Company header ─────────────────────────────────────────────────────
    price = fund.get("current_price")
    chg_1d = tech.get("price_change_1d")

    h1, h2, h3 = st.columns([3, 1.5, 1.5])
    with h1:
        st.markdown(f"## {fund.get('company_name', ticker_input)}")
        st.caption(f"**{ticker_input}**  ·  {fund.get('sector','N/A')}  ·  {fund.get('industry','N/A')}")
    with h2:
        st.metric(
            "Kurs",
            f"${price:,.2f}" if price else "N/A",
            delta=f"{chg_1d:+.2f}%" if chg_1d is not None else None,
        )
    with h3:
        hi = fund.get("week_52_high")
        lo = fund.get("week_52_low")
        st.metric("52W Range", f"${lo:,.0f} – ${hi:,.0f}" if hi and lo else "N/A")

    # ── Score-Übersicht ────────────────────────────────────────────────────
    def score_color(s):
        if s is None: return "⚪"
        return "🟢" if s >= 70 else "🟡" if s >= 50 else "🔴"

    sc1, sc2 = st.columns(2)
    with sc1:
        lt_val = lt["score"]
        st.markdown(f"**Long-Term Score** {score_color(lt_val)}",
                    help="Bewertet die fundamentale Qualität und Bewertung des Unternehmens — geeignet für Investitionsentscheidungen mit Zeithorizont 1–5+ Jahre.\n\n**Gewichtung:**\nQuality (ROIC, Margen, Cash Conversion): 45%\nValue (FCF-Yield, Earnings Yield): 30%\nSafety (Verschuldung): 15%\nMomentum-Bestätigung: 10%\n\n**Interpretation:**\n🟢 70–100 = Kaufwürdig (Buffett/Lynch-Kriterien erfüllt)\n🟡 50–69 = Abwarten (einzelne Schwächen)\n🔴 0–49 = Nicht kaufen (fundamentale Red Flags)\n\nFehlende Kennzahlen werden nicht als 0 gewertet, sondern die vorhandenen Gewichte werden renormalisiert.")
        st.progress((lt_val or 0) / 100, text=f"{lt_val}/100" if lt_val else "N/A")
        if lt["available_pct"] < 100:
            st.caption(f"ℹ️ {lt['available_pct']}% der Gewichte bewertet — fehlende Daten renormalisiert")
    with sc2:
        st_val = st_sc["score"]
        st.markdown(f"**Short-Term Score** {score_color(st_val)}",
                    help="Bewertet technisches Momentum und kurzfristige Signale — geeignet für Einstiegszeitpunkt und Trading-Entscheidungen (Wochen bis Monate).\n\n**Gewichtung:**\nMomentum (12M + 6M Preisrendite): 40%\nTechnicals (RSI, MA-Lage): 20%\nMean-Reversion (1M Reversal): 10%\nEarnings Revisions/Surprise: 30% — via kostenloser API nicht verfügbar, renormalisiert\n\n**Interpretation:**\n🟢 70–100 = Klares Long-Signal (Momentum intakt)\n🟡 50–69 = Gemischtes Bild (abwarten oder kleiner Einstieg)\n🔴 0–49 = Kein Long-Signal (Trend negativ)\n\n⚠️ Dieses Modell ist Long-only. Kein Short-Signal wird gegeben.")
        st.progress((st_val or 0) / 100, text=f"{st_val}/100" if st_val else "N/A")
        if st_sc["available_pct"] < 100:
            st.caption(f"ℹ️ {st_sc['available_pct']}% der Gewichte bewertet — Earnings Revisions nicht verfügbar")

    st.divider()

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab_chart, tab_fund, tab_tech, tab_ki = st.tabs(
        ["📊 Chart", "📋 Fundamentals", "📉 Technisch", "🤖 KI-Empfehlung"]
    )

    # ── Chart ──────────────────────────────────────────────────────────────
    with tab_chart:
        rows = 3 if tech.get("rsi_series") is not None else 2
        row_heights = [0.6, 0.2, 0.2] if rows == 3 else [0.7, 0.3]

        fig = make_subplots(
            rows=rows, cols=1, shared_xaxes=True,
            row_heights=row_heights, vertical_spacing=0.04,
            subplot_titles=["Kurs", "Volumen", "RSI (14)"][:rows],
        )

        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Kurs",
                                 line=dict(color="#1f77b4", width=2)), row=1, col=1)

        if tech.get("ma50_series") is not None:
            fig.add_trace(go.Scatter(x=hist.index, y=tech["ma50_series"], name="MA50",
                                     line=dict(color="orange", width=1.5, dash="dot")), row=1, col=1)
        if tech.get("ma200_series") is not None:
            fig.add_trace(go.Scatter(x=hist.index, y=tech["ma200_series"], name="MA200",
                                     line=dict(color="red", width=1.5, dash="dash")), row=1, col=1)

        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volumen",
                             marker_color="lightsteelblue", opacity=0.7), row=2, col=1)

        if rows == 3:
            fig.add_trace(go.Scatter(x=hist.index, y=tech["rsi_series"], name="RSI",
                                     line=dict(color="purple", width=1.5)), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.4, row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.4, row=3, col=1)
            fig.update_yaxes(range=[0, 100], row=3, col=1)

        fig.update_layout(height=580, template="plotly_white", hovermode="x unified",
                          legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                          margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # ── Fundamentals ───────────────────────────────────────────────────────
    with tab_fund:
        st.subheader("Bewertung")
        c1, c2, c3, c4 = st.columns(4)
        peg = safe_num(fund.get("peg_ratio"))
        with c1:
            if peg is not None:
                st.metric("PEG Ratio ⭐", f"{peg:.2f}",
                          delta="Günstig" if peg < 1 else ("Fair" if peg < 2 else "Teuer"),
                          delta_color="normal" if peg < 1 else ("off" if peg < 2 else "inverse"),
                          help="Peter Lynch's wichtigste Kennzahl: KGV ÷ Gewinnwachstum. Zeigt ob du Wachstum zu einem fairen Preis kaufst.\n\n< 0.5 = Schnäppchen\n< 1.0 = günstig\n1–2 = fair bewertet\n> 2.0 = teuer")
            else:
                st.metric("PEG Ratio ⭐", "N/A",
                          help="Peter Lynch's wichtigste Kennzahl: KGV ÷ Gewinnwachstum. Zeigt ob du Wachstum zu einem fairen Preis kaufst.\n\n< 0.5 = Schnäppchen\n< 1.0 = günstig\n1–2 = fair bewertet\n> 2.0 = teuer")
        with c2:
            st.metric("P/E (trailing)", fmt_num(fund.get("pe_ratio")),
                      help="Kurs-Gewinn-Verhältnis der letzten 12 Monate. Wie viel du für 1 EUR Gewinn bezahlst. Immer im Branchenvergleich lesen — Tech hat höhere KGVs als Industrie. Allein wenig aussagekräftig, immer mit PEG kombinieren.")
        with c3:
            st.metric("P/E (forward)", fmt_num(fund.get("forward_pe")),
                      help="Kurs geteilt durch den erwarteten Gewinn der nächsten 12 Monate (Analysten-Konsens). Niedriger als trailing P/E = Markt erwartet Gewinnwachstum. Deutlich niedriger = attraktiv.")
        with c4:
            roe = safe_num(fund.get("roe"))
            if roe is not None:
                roe_pct = roe * 100
                st.metric("ROE", f"{roe_pct:.1f}%",
                          delta="Stark" if roe_pct > 15 else "Schwach",
                          delta_color="normal" if roe_pct > 15 else "inverse",
                          help="Return on Equity — Eigenkapitalrendite. Wie effizient erzeugt das Management Gewinn aus dem eingesetzten Kapital der Aktionäre.\n\nBuffett-Kriterium: > 15% über mehrere Jahre = starkes Unternehmen mit Wettbewerbsvorteil (Moat). > 30% = außergewöhnlich.")
            else:
                st.metric("ROE", "N/A",
                          help="Return on Equity — Eigenkapitalrendite. Wie effizient erzeugt das Management Gewinn aus dem eingesetzten Kapital.\n\nBuffett-Kriterium: > 15% = starkes Unternehmen.")

        st.subheader("Wachstum & Profitabilität")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            rg = safe_num(fund.get("revenue_growth"))
            st.metric("Umsatzwachstum", f"{rg*100:+.1f}%" if rg is not None else "N/A",
                      delta_color=delta_color(rg),
                      help="Umsatzwachstum gegenüber dem Vorjahr. Zeigt ob das Kerngeschäft wirklich wächst. Lynch sucht nach Unternehmen mit 20–25% Wachstum. Wichtig: Wachstum muss profitabel sein — daher immer mit Nettomarge kombinieren.")
        with c2:
            eg = safe_num(fund.get("earnings_growth"))
            st.metric("Gewinnwachstum", f"{eg*100:+.1f}%" if eg is not None else "N/A",
                      delta_color=delta_color(eg),
                      help="Gewinnwachstum gegenüber dem Vorjahr. Wichtiger als Umsatzwachstum — zeigt ob das Unternehmen profitabler wird. Steigt der Umsatz aber nicht der Gewinn, verliert das Unternehmen Effizienz. > 15% p.a. über mehrere Jahre = Qualitätszeichen.")
        with c3:
            mg = safe_num(fund.get("profit_margin"))
            st.metric("Nettomarge", f"{mg*100:.1f}%" if mg is not None else "N/A",
                      help="Wie viel Prozent des Umsatzes als Nettogewinn übrig bleibt. Zeigt die Qualität des Geschäftsmodells.\n\n< 5% = niedrig (Handel, Airlines)\n10–20% = gut\n> 20% = exzellent (Software, Pharma)\n\nHohe Margen + Preismacht = Burggraben (Moat).")
        with c4:
            fcf = safe_num(fund.get("free_cash_flow"))
            st.metric("Free Cash Flow", fmt_money(fcf),
                      delta="Positiv" if fcf and fcf > 0 else ("Negativ" if fcf else None),
                      delta_color=delta_color(fcf),
                      help="Freier Cashflow = Operativer Cashflow minus Investitionen. Das echte Geld, das das Unternehmen verdient — schwerer zu manipulieren als Buchwinn. Buffett nennt es 'Owner Earnings'. Positiv und wachsend = gesundes Unternehmen.")

        st.subheader("Finanzielle Gesundheit")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            de = fund.get("debt_to_equity")
            if de is not None:
                st.metric("Debt/Equity", f"{de:.2f}",
                          delta="Sicher" if de < 0.5 else ("OK" if de < 1 else "Hoch"),
                          delta_color="normal" if de < 0.5 else ("off" if de < 1 else "inverse"),
                          help="Verschuldungsgrad: Gesamtschulden ÷ Eigenkapital. Zeigt wie stark das Unternehmen fremdfinanziert ist.\n\n< 0.5 = konservativ, sicher\n0.5–1.0 = akzeptabel\n> 2.0 = riskant, besonders bei steigenden Zinsen\n\nAusnahme: Banken und Versorger haben strukturell hohe Werte.")
            else:
                st.metric("Debt/Equity", "N/A",
                          help="Verschuldungsgrad: Gesamtschulden ÷ Eigenkapital.\n\n< 0.5 = konservativ\n0.5–1.0 = akzeptabel\n> 2.0 = riskant")
        with c2:
            beta = safe_num(fund.get("beta"))
            st.metric("Beta", f"{beta:.2f}" if beta is not None else "N/A",
                      help="Volatilität der Aktie im Vergleich zum Gesamtmarkt (S&P 500).\n\nBeta = 1.0 = bewegt sich wie der Markt\nBeta > 1.0 = volatiler als der Markt (mehr Chance & Risiko)\nBeta < 1.0 = defensiver als der Markt (z.B. Versorger, Pharma)\nBeta < 0 = bewegt sich gegen den Markt (selten)")
        with c3:
            dy = safe_num(fund.get("dividend_yield"))
            st.metric("Dividende", f"{dy*100:.2f}%" if dy is not None else "Keine",
                      help="Jährliche Dividendenausschüttung in % des aktuellen Kurses. Interessant für Einkommens-Investoren.\n\nVorsicht: Eine sehr hohe Dividende (> 6%) kann auf finanzielle Probleme hindeuten oder nicht nachhaltig sein. Buffett bevorzugt Unternehmen, die Gewinne reinvestieren statt ausschütten.")
        with c4:
            st.metric("Market Cap", fmt_money(safe_num(fund.get("market_cap"))),
                      help="Börsenwert = Aktueller Kurs × Anzahl Aktien. Größenklassen:\n\nMicro Cap: < 300 Mio (sehr riskant, illiquide)\nSmall Cap: 300 Mio – 2 Mrd\nMid Cap: 2–10 Mrd\nLarge Cap: 10–200 Mrd\nMega Cap: > 200 Mrd\n\nLynch's Tipp: Small & Mid Caps haben oft mehr Wachstumspotenzial.")

        # ── Neue Modell-Metriken ────────────────────────────────────────────
        st.subheader("Value-Metriken (Modell)")
        ev = safe_num(fund.get("enterprise_value"))
        fcf = safe_num(fund.get("free_cash_flow"))
        ebitda = safe_num(fund.get("ebitda"))
        ni = safe_num(fund.get("net_income"))
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            fy = (fcf / ev * 100) if fcf and ev and ev > 0 else None
            st.metric("FCF-Yield ⭐", f"{fy:.1f}%" if fy is not None else "N/A",
                      delta="Attraktiv" if fy and fy >= 4 else ("Fair" if fy and fy >= 2 else None),
                      delta_color="normal" if fy and fy >= 4 else "off",
                      help="Free Cash Flow ÷ Enterprise Value. Wie viel echten Cash wirft das Unternehmen pro investiertem Euro ab.\n\n> 6% = sehr attraktiv\n> 4% = attraktiv\n> 2% = fair\n< 2% = teuer\n\nGreenblatt (Magic Formula): FCF-Yield ist eine der verlässlichsten Value-Kennzahlen.")
        with c2:
            ey = (ebitda / ev * 100) if ebitda and ev and ev > 0 else None
            st.metric("Earnings Yield", f"{ey:.1f}%" if ey is not None else "N/A",
                      delta="Attraktiv" if ey and ey >= 5 else None,
                      delta_color="normal" if ey and ey >= 5 else "off",
                      help="EBITDA ÷ Enterprise Value (Greenblatt Magic Formula). Misst die operative Ertragskraft unabhängig von Kapitalstruktur und Steuern.\n\n> 8% = sehr attraktiv\n> 5% = attraktiv\n< 3% = teuer")
        with c3:
            cc = (fcf / ni * 100) if fcf and ni and ni > 0 else None
            st.metric("Cash Conversion", f"{cc:.0f}%" if cc is not None else "N/A",
                      delta="Gut" if cc and cc >= 90 else ("Schwach" if cc and cc < 70 else None),
                      delta_color="normal" if cc and cc >= 90 else ("inverse" if cc and cc < 70 else "off"),
                      help="Free Cash Flow ÷ Net Income. Zeigt ob die ausgewiesenen Gewinne auch wirklich als Cash ankommen — schwerer zu manipulieren als Buchwinn.\n\n≥ 100% = exzellent (Terry Smith Benchmark)\n≥ 90% = gut\n< 70% = Warning: Gewinn wird nicht als Cash realisiert")
        with c4:
            td = safe_num(fund.get("total_debt"))
            tc = safe_num(fund.get("total_cash"))
            if td is not None and ebitda and ebitda > 0:
                nd = td - (tc or 0)
                nde = nd / ebitda
                st.metric("Net Debt/EBITDA", f"{nde:.1f}x",
                          delta="Sicher" if nde <= 1 else ("Hoch" if nde > 3 else None),
                          delta_color="normal" if nde <= 1 else ("inverse" if nde > 3 else "off"),
                          help="Nettoverschuldung (Schulden − Cash) ÷ EBITDA. Zeigt in wie vielen Jahren das Unternehmen seine Schulden aus dem operativen Gewinn tilgen könnte.\n\n< 0 = Netto-Cash-Position (exzellent)\n< 1.5x = gut\n< 3x = akzeptabel\n> 3x = Red Flag (Buffett/Munger meiden solche Bilanzen)")
            else:
                st.metric("Net Debt/EBITDA", "N/A",
                          help="Nettoverschuldung ÷ EBITDA.\n\n< 1.5x = gut · > 3x = Red Flag")

        # ── Long-Term Score Breakdown ────────────────────────────────────────
        st.subheader("Long-Term Score Breakdown")
        st.caption("Quality 45% · Value 30% · Safety 15% · Momentum 10% — fehlende Kennzahlen werden renormalisiert, nicht als 0 gewertet")
        col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 4])
        col_a.markdown("**Kennzahl**")
        col_b.markdown("**Wert**")
        col_c.markdown("**Score · Gewicht**")
        col_d.markdown("**Benchmark**")
        st.divider()
        for name, comp in lt["components"].items():
            col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 4])
            with col_a:
                st.write(f"**{name}**")
            with col_b:
                st.write(comp["label"])
            with col_c:
                if comp["score"] is not None:
                    color = "🟢" if comp["score"] >= 70 else "🟡" if comp["score"] >= 40 else "🔴"
                    st.write(f"{color} {comp['score']}/100 · {comp['weight']*100:.0f}%")
                else:
                    st.write("⚪ N/A")
            with col_d:
                st.caption(comp.get("benchmark", ""))

    # ── Technisch ──────────────────────────────────────────────────────────
    with tab_tech:
        st.subheader("Momentum & Trend")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            rsi = tech.get("rsi")
            if rsi is not None:
                label = "Überverkauft 🟢" if rsi < 30 else ("Überkauft 🔴" if rsi > 70 else "Neutral ⚪")
                st.metric("RSI (14)", f"{rsi:.1f}", delta=label, delta_color="off",
                          help="Relative Strength Index — misst ob eine Aktie überkauft oder überverkauft ist. Skala 0–100.\n\n< 30 = überverkauft → potenzielle Kaufgelegenheit\n30–70 = neutrales Territorium\n> 70 = überkauft → Rücksetzer möglich\n\nFunktioniert am besten in Seitwärtsmärkten. In starken Trends kann der RSI lange überkauft bleiben.")
            else:
                st.metric("RSI (14)", "N/A",
                          help="Relative Strength Index — misst ob eine Aktie überkauft oder überverkauft ist.\n\n< 30 = überverkauft (Kaufgelegenheit)\n> 70 = überkauft (Vorsicht)")
        with c2:
            mt = tech.get("macd_trend")
            if mt:
                st.metric("MACD", mt,
                          delta="Bullish ↗" if mt == "Bullish" else "Bearish ↘",
                          delta_color="normal" if mt == "Bullish" else "inverse",
                          help="Moving Average Convergence/Divergence — Trendfolge-Indikator der Momentum und Trendrichtung zeigt.\n\nBullish = MACD-Linie liegt über der Signallinie (positives Histogram) → Aufwärtsdruck\nBearish = MACD-Linie liegt unter der Signallinie → Abwärtsdruck\n\nBestes Signal: Wenn MACD von unten nach oben die Nulllinie kreuzt.")
            else:
                st.metric("MACD", "N/A",
                          help="Moving Average Convergence/Divergence — Trendfolge-Indikator.\n\nBullish = Aufwärtsmomentum\nBearish = Abwärtsmomentum")
        with c3:
            pvm = tech.get("price_vs_ma200")
            st.metric("Kurs vs MA200", f"{pvm:+.1f}%" if pvm is not None else "N/A",
                      delta_color=delta_color(pvm),
                      help="Abstand des aktuellen Kurses vom 200-Tage-Durchschnitt (gleitender Mittelwert über ~10 Monate).\n\n> 0% = Kurs über MA200 → langfristiger Aufwärtstrend intakt\n< 0% = Kurs unter MA200 → Abwärtstrend\n\nDer wichtigste Trendindikator für langfristige Investoren. Buffett kauft keine Aktien, die im Abwärtstrend sind.")
        with c4:
            cs = tech.get("cross_signal")
            if cs:
                is_golden = "Golden" in cs
                st.metric("MA Cross", cs,
                          delta="Bullish" if is_golden else "Bearish",
                          delta_color="normal" if is_golden else "inverse",
                          help="Verhältnis des 50-Tage- zum 200-Tage-Durchschnitt.\n\nGolden Cross (MA50 > MA200) = bullisches Langzeitsignal → institutionelle Investoren kaufen\nDeath Cross (MA50 < MA200) = bearisches Signal → langfristiger Abwärtstrend\n\nGolden Cross ist eine der zuverlässigsten technischen Signale für Trendwechsel.")
            else:
                st.metric("MA Cross", "N/A",
                          help="Verhältnis MA50 zu MA200.\n\nGolden Cross = bullisch\nDeath Cross = bearisch")

        st.subheader("Performance")
        c1, c2, c3 = st.columns(3)
        with c1:
            p = tech.get("price_change_1d")
            st.metric("1 Tag", f"{p:+.2f}%" if p is not None else "N/A", delta_color=delta_color(p),
                      help="Kursveränderung gegenüber dem gestrigen Schlusskurs. Kurzfristiges Tagesrauschen — für langfristige Investoren kaum relevant, aber nützlich um aktuelle Marktstimmung einzuschätzen.")
        with c2:
            p = tech.get("price_change_1m")
            st.metric("1 Monat", f"{p:+.2f}%" if p is not None else "N/A", delta_color=delta_color(p),
                      help="Kursveränderung der letzten 22 Handelstage. Zeigt kurzfristiges Momentum. Ein starker Anstieg von > 15% in einem Monat erhöht das Rücksetzer-Risiko (RSI oft überkauft).")
        with c3:
            p6 = tech.get("price_change_6m")
            st.metric("6 Monate", f"{p6:+.2f}%" if p6 is not None else "N/A", delta_color=delta_color(p6),
                      help="6-Monats-Momentum (126 Handelstage). Wichtige Komponente des Short-Term Scores. Positiv + beschleunigend = starkes Kaufsignal im Momentum-Modell.")

        c1, c2 = st.columns(2)
        with c1:
            p = tech.get("price_change_1d")
            st.metric("1 Tag", f"{p:+.2f}%" if p is not None else "N/A", delta_color=delta_color(p),
                      help="Kursveränderung gegenüber dem gestrigen Schlusskurs. Kurzfristiges Tagesrauschen — für langfristige Investoren kaum relevant.")
        with c2:
            p = tech.get("price_change_1y")
            st.metric("1 Jahr", f"{p:+.2f}%" if p is not None else "N/A", delta_color=delta_color(p),
                      help="12-Monats-Momentum (minus letzter Monat = 12-1). Wichtigste Komponente im Short-Term Scoring-Modell. Top-Dezil des Marktes = starkes Long-Signal.")

        # MACD Chart
        if tech.get("macd_series") is not None:
            st.subheader("MACD")
            mfig = go.Figure()
            mfig.add_trace(go.Scatter(x=hist.index, y=tech["macd_series"],
                                      name="MACD", line=dict(color="blue")))
            mfig.add_trace(go.Scatter(x=hist.index, y=tech["signal_series"],
                                      name="Signal", line=dict(color="orange")))
            hist_vals = tech["macd_hist_series"].fillna(0)
            mfig.add_trace(go.Bar(x=hist.index, y=hist_vals, name="Histogram",
                                  marker_color=["green" if v > 0 else "red" for v in hist_vals]))
            mfig.update_layout(height=280, template="plotly_white",
                               hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(mfig, use_container_width=True)

        # Short-Term Score Breakdown
        st.subheader("Short-Term Score Breakdown")
        st.caption("Momentum 40% · Technicals 20% · Mean-Reversion 10% · Earnings Revisions/Surprise 30% — letztere nicht verfügbar, renormalisiert")
        col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 4])
        col_a.markdown("**Kennzahl**")
        col_b.markdown("**Wert**")
        col_c.markdown("**Score · Gewicht**")
        col_d.markdown("**Benchmark**")
        st.divider()
        for name, comp in st_sc["components"].items():
            col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 4])
            with col_a:
                st.write(f"**{name}**")
            with col_b:
                st.write(comp["label"])
            with col_c:
                if comp["score"] is not None:
                    color = "🟢" if comp["score"] >= 70 else "🟡" if comp["score"] >= 40 else "🔴"
                    st.write(f"{color} {comp['score']}/100 · {comp['weight']*100:.0f}%")
                else:
                    st.write("⚪ N/A")
            with col_d:
                st.caption(comp.get("benchmark", ""))

        # News + Sentiment
        if news:
            st.subheader("Aktuelle News & Sentiment")

            # Gesamtstimmung
            overall_score = sent.get("overall_score")
            overall_label = sent.get("overall_label")
            zusammenfassung = sent.get("zusammenfassung")

            if overall_score is not None:
                if overall_score >= 0.3:
                    st.success(f"**News-Stimmung: {overall_label}** ({overall_score:+.2f}) — {zusammenfassung}")
                elif overall_score <= -0.3:
                    st.error(f"**News-Stimmung: {overall_label}** ({overall_score:+.2f}) — {zusammenfassung}")
                else:
                    st.info(f"**News-Stimmung: {overall_label}** ({overall_score:+.2f}) — {zusammenfassung}")

            # Sentiment-Map für schnellen Lookup
            sent_map = {item["id"]: item for item in sent.get("items", [])}

            for i, n in enumerate(news):
                item = sent_map.get(i + 1, {})
                s_val = item.get("score")
                s_label = item.get("sentiment", "")
                grund = item.get("grund", "")

                if s_val is not None and s_val >= 0.3:
                    badge = "🟢"
                elif s_val is not None and s_val <= -0.3:
                    badge = "🔴"
                elif s_val is not None:
                    badge = "🟡"
                else:
                    badge = "⚪"

                date_str = f" · {n['date']}" if n.get("date") else ""
                pub_str = f" *({n['publisher']})*" if n.get("publisher") else ""
                st.markdown(f"{badge} **{n['title']}**{pub_str}{date_str}")
                if grund:
                    st.caption(f"→ {grund}")

    # ── KI-Empfehlung ──────────────────────────────────────────────────────
    with tab_ki:
        # ── Entscheidungsbrücke ─────────────────────────────────────────────
        st.subheader("Entscheidungslogik")
        st.caption("So führen die Scores mechanisch zum Verdict — bevor Claude qualitativ interpretiert")

        col_lt, col_st = st.columns(2)

        with col_lt:
            st.markdown("**Long-Term Regeln**")
            for rule in decision["lt_rules"]:
                icon = "✅" if rule["ok"] else "❌"
                st.markdown(f"{icon} **{rule['label']}**")
                st.caption(f"→ {rule['value']} — {rule['note']}")

        with col_st:
            st.markdown("**Short-Term Regeln**")
            for rule in decision["st_rules"]:
                icon = "✅" if rule["ok"] else "❌"
                st.markdown(f"{icon} **{rule['label']}**")
                st.caption(f"→ {rule['value']} — {rule['note']}")

        mv = decision["mechanical_verdict"]
        if mv == "KAUFEN":
            st.success(f"**Mechanisches Signal: {mv}** — {decision['verdict_reason']}")
        elif mv == "NICHT KAUFEN":
            st.error(f"**Mechanisches Signal: {mv}** — {decision['verdict_reason']}")
        else:
            st.warning(f"**Mechanisches Signal: {mv}** — {decision['verdict_reason']}")

        st.caption("↓ Claude berücksichtigt zusätzlich: Moat-Substanz, Management, Disruptionsrisiko, Makro-Kontext, News")
        st.divider()

        # ── Claude-Analyse ──────────────────────────────────────────────────
        st.subheader("KI-Analyse")
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEY nicht gesetzt. Bitte `.env` Datei anlegen.")
        else:
            with st.spinner("Claude analysiert …"):
                try:
                    result = get_recommendation(ticker_input, fund, tech, mode, news, lt, st_sc, sent)
                    verdict = result["verdict"]

                    if verdict == "KAUFEN":
                        st.success("## 🟢  KAUFEN")
                    elif verdict == "NICHT KAUFEN":
                        st.error("## 🔴  NICHT KAUFEN")
                    else:
                        st.warning("## 🟡  ABWARTEN")

                    st.markdown("---")

                    # Escape $ amounts so Streamlit doesn't render them as LaTeX
                    import re
                    display_text = result["full_text"]
                    # Remove the VERDICT line (already shown above)
                    display_text = re.sub(r"VERDICT:.*\n?", "", display_text).strip()
                    # Escape dollar signs before numbers (e.g. $270 → \$270)
                    display_text = re.sub(r"\$(\d)", r"\\$\1", display_text)
                    st.markdown(display_text)
                except Exception as e:
                    st.error(f"Fehler bei KI-Analyse: {e}")

# ── Welcome screen ─────────────────────────────────────────────────────────────
elif not ticker_input:
    st.markdown("""
### So funktioniert es
1. **Ticker eingeben** — z.B. `AAPL`, `MSFT`, `NVDA`, `BRK-B`
2. **Modus wählen** — Long-Term für Investments, Short-Term für Trading, Beides für vollständige Analyse
3. **Analysieren klicken** — Dashboard + KI-Empfehlung nach Buffett & Lynch

---
**Beliebte Ticker:** `AAPL` · `MSFT` · `NVDA` · `AMZN` · `GOOGL` · `BRK-B` · `JNJ` · `META`
""")
