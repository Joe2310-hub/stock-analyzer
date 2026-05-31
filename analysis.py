import os
import anthropic


def get_recommendation(
    ticker: str,
    fundamentals: dict,
    technicals: dict,
    mode: str,
    news: list,
    lt_score: dict,
    st_score: dict,
    sentiment: dict = None,
) -> dict:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    f = fundamentals
    t = technicals

    def fmt_pct(val, multiply=True):
        if val is None:
            return "N/A"
        return f"{val * 100:+.1f}%" if multiply else f"{val:+.1f}%"

    def fmt_money(val):
        if val is None:
            return "N/A"
        if abs(val) >= 1e12:
            return f"${val/1e12:.2f}T"
        if abs(val) >= 1e9:
            return f"${val/1e9:.1f}B"
        return f"${val/1e6:.0f}M"

    def fmt_num(val, decimals=2):
        return f"{val:.{decimals}f}" if val is not None else "N/A"

    # Score-Breakdown formatieren
    def fmt_breakdown(score_dict):
        lines = []
        for name, comp in score_dict["components"].items():
            if comp["score"] is not None:
                lines.append(f"  {name}: {comp['label']} → {comp['score']}/100 (Gewicht {comp['weight']*100:.0f}%)")
            else:
                lines.append(f"  {name}: N/A → nicht bewertet (renormalisiert)")
        return "\n".join(lines)

    sent = sentiment or {}
    overall_sent = sent.get("overall_label")
    overall_score_sent = sent.get("overall_score")
    sent_map = {item["id"]: item for item in sent.get("items", [])}

    news_lines = []
    for i, n in enumerate(news or []):
        item = sent_map.get(i + 1, {})
        score_str = f" [Sentiment: {item.get('sentiment', '?')} {item.get('score', 0):+.1f}]" if item else ""
        news_lines.append(f"- {n['title']}{score_str}")
    news_block = "\n".join(news_lines) if news_lines else "Keine News verfügbar"

    sentiment_block = (
        f"Gesamtstimmung der News: {overall_sent} ({overall_score_sent:+.2f})\n{sent.get('zusammenfassung', '')}"
        if overall_sent else "News-Sentiment: nicht verfügbar"
    )

    # FCF/EV und EBITDA/EV berechnen für Prompt
    ev = f.get("enterprise_value")
    fcf = f.get("free_cash_flow")
    ebitda = f.get("ebitda")
    fcf_yield = (fcf / ev * 100) if fcf and ev and ev > 0 else None
    earnings_yield = (ebitda / ev * 100) if ebitda and ev and ev > 0 else None
    cash_conversion = (fcf / f["net_income"] * 100) if fcf and f.get("net_income") and f["net_income"] > 0 else None
    net_debt = (f.get("total_debt", 0) or 0) - (f.get("total_cash", 0) or 0)
    net_debt_ebitda = (net_debt / ebitda) if ebitda and ebitda > 0 else None

    prompt = f"""Du bist ein erfahrener Investmentanalyst. Du verwendest das folgende Scoring-Modell (STOCK_ANALYSIS_MODEL):

LONG-TERM Score: {lt_score['score']}/100 (basiert auf {lt_score['available_pct']}% der Gewichte)
SHORT-TERM Score: {st_score['score']}/100 (basiert auf {st_score['available_pct']}% der Gewichte)

LONG-TERM Breakdown (Quality 45% · Value 30% · Safety 15% · Momentum 10%):
{fmt_breakdown(lt_score)}

SHORT-TERM Breakdown (Momentum 40% · Technicals 30% · Mean-Reversion 10% | Revisions 30% nicht verfügbar → renormalisiert):
{fmt_breakdown(st_score)}

TICKER: {ticker} | {f.get('company_name')} | {f.get('sector')} · {f.get('industry')}
MODUS: {mode}

--- ROHDATEN FUNDAMENTALS ---
Kurs/EV:        ${fmt_num(f.get('current_price'))} | EV: {fmt_money(ev)}
FCF-Yield:      {f"{fcf_yield:.1f}%" if fcf_yield is not None else "N/A"}
Earnings Yield: {f"{earnings_yield:.1f}%" if earnings_yield is not None else "N/A"} (EBITDA/EV)
Cash Conversion:{f"{cash_conversion:.0f}%" if cash_conversion is not None else "N/A"} (FCF/NI)
ROIC/ROE:       {fmt_pct(f.get('roe'))}
Bruttomarge:    {fmt_pct(f.get('gross_margin'))}
Op. Marge:      {fmt_pct(f.get('operating_margin'))}
Net Margin:     {fmt_pct(f.get('profit_margin'))}
Net Debt/EBITDA:{f"{net_debt_ebitda:.1f}x" if net_debt_ebitda is not None else "N/A"}
PEG Ratio:      {fmt_num(f.get('peg_ratio'))}
Umsatzwachstum: {fmt_pct(f.get('revenue_growth'))}
Gewinnwachstum: {fmt_pct(f.get('earnings_growth'))}

--- ROHDATEN TECHNISCH ---
RSI (14):       {fmt_num(t.get('rsi'), 1)}
MACD:           {t.get('macd_trend', 'N/A')}
Kurs vs MA200:  {f"{t.get('price_vs_ma200', 0):+.1f}%" if t.get('price_vs_ma200') is not None else "N/A"}
MA Cross:       {t.get('cross_signal', 'N/A')}
Perf. 1M:       {f"{t.get('price_change_1m', 0):+.1f}%" if t.get('price_change_1m') is not None else "N/A"}
Perf. 6M:       {f"{t.get('price_change_6m', 0):+.1f}%" if t.get('price_change_6m') is not None else "N/A"}
Perf. 12M:      {f"{t.get('price_change_1y', 0):+.1f}%" if t.get('price_change_1y') is not None else "N/A"}

--- NEWS & SENTIMENT ---
{sentiment_block}
{news_block}

--- AUFGABE ---
{"Fokus: Long-Term Score und fundamentale Qualität." if "Long" in mode else "Fokus: Short-Term Score und technisches Momentum." if "Short" in mode else "Bewerte beide Tracks gleichwertig."}

Regeln:
- Keine Short-Empfehlungen (Long-only Modell)
- Weise am Ende auf qualitative Faktoren hin, die das Scoring nicht erfasst (Moat, Management, Disruption)
- Sei konkret, nenn Zahlenwerte, keine Floskeln

Antworte auf Deutsch in exakt diesem Format:

VERDICT: [KAUFEN / ABWARTEN / NICHT KAUFEN]
SCORE: LT {lt_score['score']}/100 · ST {st_score['score']}/100

ZUSAMMENFASSUNG:
[2-3 Sätze. Die wichtigsten Score-Treiber zuerst. Konkrete Zahlen.]

STÄRKEN:
- [mit konkretem Wert]
- [mit konkretem Wert]
- [weiterer falls vorhanden]

RISIKEN:
- [mit konkretem Wert]
- [mit konkretem Wert]
- [weiterer falls vorhanden]

QUALITATIVE OFFENE FRAGEN:
- [Was das Modell nicht erfasst — Moat, Management, Disruption, Regulierung]
- [max. 2 Punkte]

FAZIT:
[1 konkreter Satz: Was jetzt tun?]
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text

    verdict = "ABWARTEN"
    for line in response_text.splitlines():
        upper = line.upper()
        if "VERDICT:" in upper:
            if "NICHT KAUFEN" in upper:
                verdict = "NICHT KAUFEN"
            elif "KAUFEN" in upper:
                verdict = "KAUFEN"
            elif "ABWARTEN" in upper:
                verdict = "ABWARTEN"
            break

    return {"verdict": verdict, "full_text": response_text}
