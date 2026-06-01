"""
Zweigleisiges Scoring-Modell nach STOCK_ANALYSIS_MODEL.md.

Long-Term:  Quality 45% · Value 30% · Safety 15% · Momentum 10%
Short-Term: Momentum 40% · Technicals/Sentiment 30% · Mean-Reversion 10%
            (Earnings Revisions 20% + Surprise 10% via freier API nicht verfügbar → renormalisiert)
"""


def decision_logic(lt: dict, st: dict, fund: dict, tech: dict) -> dict:
    """
    Wendet die Entscheidungsregeln aus dem Modell mechanisch an.
    Gibt ein strukturiertes Ergebnis zurück das den Weg vom Score zum Verdict zeigt.
    """
    lt_val = lt["score"] or 0
    st_val = st["score"] or 0

    ev = fund.get("enterprise_value")
    fcf = fund.get("free_cash_flow")
    ebitda = fund.get("ebitda")
    td = fund.get("total_debt")
    tc = fund.get("total_cash")

    fcf_yield = (fcf / ev * 100) if fcf and ev and ev > 0 else None
    earnings_yield_val = (ebitda / ev * 100) if ebitda and ev and ev > 0 else None
    net_debt = (td or 0) - (tc or 0) if td is not None else None
    net_debt_ebitda = (net_debt / ebitda) if net_debt is not None and ebitda and ebitda > 0 else None

    # ── Long-Term Regeln ──────────────────────────────────────────────────
    lt_rules = []

    r1_ok = lt_val >= 70
    lt_rules.append({
        "label": f"Long-Term Score ≥ 70",
        "value": f"{lt_val}/100",
        "ok": r1_ok,
        "note": "Grundbedingung für Kaufsignal" if r1_ok else "Unter Kaufschwelle — fundamentale Schwächen"
    })

    value_ok = (fcf_yield is not None and fcf_yield >= 4) or (earnings_yield_val is not None and earnings_yield_val >= 5)
    vy_parts = []
    if fcf_yield is not None:
        vy_parts.append(f"FCF-Yield {fcf_yield:.1f}%")
    if earnings_yield_val is not None:
        vy_parts.append(f"Earnings Yield {earnings_yield_val:.1f}%")
    lt_rules.append({
        "label": "Bewertung attraktiv (FCF-Yield ≥ 4% oder Earnings Yield ≥ 5%)",
        "value": " · ".join(vy_parts) if vy_parts else "N/A",
        "ok": value_ok,
        "note": "Mindestens eine Value-Kennzahl im attraktiven Bereich" if value_ok else "Zu teuer — kein ausreichender Sicherheitspuffer (Margin of Safety)"
    })

    balance_ok = (net_debt_ebitda is None or net_debt_ebitda < 3)
    lt_rules.append({
        "label": "Keine Bilanz-Red-Flag (Net Debt/EBITDA < 3x)",
        "value": f"{net_debt_ebitda:.1f}x" if net_debt_ebitda is not None else "N/A",
        "ok": balance_ok,
        "note": "Bilanz solide" if balance_ok else "⚠️ Hohe Verschuldung — Red Flag"
    })

    lt_signal_kaufen = r1_ok and balance_ok
    lt_signal_stark = lt_signal_kaufen and value_ok

    # ── Short-Term Regeln ─────────────────────────────────────────────────
    st_rules = []

    r_st_ok = st_val >= 70
    st_rules.append({
        "label": "Short-Term Score ≥ 70",
        "value": f"{st_val}/100",
        "ok": r_st_ok,
        "note": "Klares Momentum-Kaufsignal" if r_st_ok else "Momentum schwach — kein kurzfristiges Long-Signal"
    })

    mom_ok = (tech.get("price_change_1y") or 0) > 0
    st_rules.append({
        "label": "12M-Momentum positiv",
        "value": f"{tech.get('price_change_1y', 0):+.1f}%" if tech.get("price_change_1y") is not None else "N/A",
        "ok": mom_ok,
        "note": "Aufwärtstrend bestätigt" if mom_ok else "Negativer Trend — abwarten"
    })

    ma_ok = tech.get("ma200") is not None and (tech.get("current_price") or 0) > tech.get("ma200", 0)
    st_rules.append({
        "label": "Kurs über MA200 (Trend intakt)",
        "value": lt["components"].get("12M-Momentum", {}).get("label", "N/A"),
        "ok": ma_ok,
        "note": "Langfristiger Aufwärtstrend intakt" if ma_ok else "Unter MA200 — Abwärtstrend"
    })

    # ── Gesamtverdikt ────────────────────────────────────────────────────
    if lt_signal_stark and r_st_ok:
        mechanical_verdict = "KAUFEN"
        verdict_reason = "Alle Kaufbedingungen erfüllt: Qualität, Bewertung, Bilanz und Momentum"
    elif lt_signal_kaufen and not value_ok and r_st_ok:
        mechanical_verdict = "ABWARTEN"
        verdict_reason = "Qualität und Momentum stark — aber Bewertung noch zu hoch. Auf Rücksetzer warten."
    elif lt_signal_kaufen and not r_st_ok:
        mechanical_verdict = "ABWARTEN"
        verdict_reason = "Fundamentals gut — Momentum fehlt noch als Timing-Bestätigung."
    elif not r1_ok and r_st_ok:
        mechanical_verdict = "ABWARTEN"
        verdict_reason = "Kurzfristiges Momentum vorhanden — aber fundamentale Basis zu schwach für Investment."
    elif not r1_ok and not r_st_ok:
        mechanical_verdict = "NICHT KAUFEN"
        verdict_reason = "Weder fundamentale Qualität noch technisches Momentum erfüllen die Kaufbedingungen."
    else:
        mechanical_verdict = "ABWARTEN"
        verdict_reason = "Gemischtes Bild — einzelne Bedingungen nicht erfüllt."

    return {
        "mechanical_verdict": mechanical_verdict,
        "verdict_reason": verdict_reason,
        "lt_rules": lt_rules,
        "st_rules": st_rules,
        "lt_signal_kaufen": lt_signal_kaufen,
        "lt_signal_stark": lt_signal_stark,
        "st_signal": r_st_ok,
    }


def _weighted(components: dict) -> dict:
    """Berechne Gesamtscore mit Re-Normalisierung fehlender Komponenten."""
    total_w = sum(c["weight"] for c in components.values() if c["score"] is not None)
    total_ws = sum(c["score"] * c["weight"] for c in components.values() if c["score"] is not None)
    score = round(total_ws / total_w) if total_w > 0 else None
    return {"score": score, "available_pct": round(total_w * 100), "components": components}


def long_term_score(fund: dict, tech: dict) -> dict:
    c = {}

    # ── ROIC / ROE — Quality 15% ─────────────────────────────────────────
    roe = fund.get("roe")
    if roe is not None:
        p = roe * 100
        s = 100 if p >= 25 else 80 if p >= 20 else 60 if p >= 15 else 40 if p >= 10 else 10
        c["ROIC/ROE"] = {"label": f"{p:.1f}%", "score": s, "weight": 0.15,
                         "benchmark": "> 15% gut · > 25% exzellent"}
    else:
        c["ROIC/ROE"] = {"label": "N/A", "score": None, "weight": 0.15,
                         "benchmark": "> 15% gut · > 25% exzellent"}

    # ── Bruttomarge — Quality 10% ────────────────────────────────────────
    gm = fund.get("gross_margin")
    if gm is not None:
        p = gm * 100
        s = 100 if p >= 60 else 75 if p >= 40 else 45 if p >= 20 else 20
        c["Bruttomarge"] = {"label": f"{p:.1f}%", "score": s, "weight": 0.10,
                            "benchmark": "> 40% gut · > 60% exzellent"}
    else:
        c["Bruttomarge"] = {"label": "N/A", "score": None, "weight": 0.10,
                            "benchmark": "> 40% gut · > 60% exzellent"}

    # ── Cash Conversion FCF/NI — Quality 10% ─────────────────────────────
    fcf = fund.get("free_cash_flow")
    ni = fund.get("net_income")
    if fcf is not None and ni is not None and ni > 0:
        cc = fcf / ni
        s = 100 if cc >= 1.0 else 80 if cc >= 0.9 else 50 if cc >= 0.7 else 20
        c["Cash Conversion"] = {"label": f"{cc*100:.0f}%", "score": s, "weight": 0.10,
                                "benchmark": "≥ 90% gut · ≥ 100% exzellent"}
    else:
        c["Cash Conversion"] = {"label": "N/A", "score": None, "weight": 0.10,
                                "benchmark": "≥ 90% gut · ≥ 100% exzellent"}

    # ── Operative Marge — Quality 10% ────────────────────────────────────
    om = fund.get("operating_margin")
    if om is not None:
        p = om * 100
        s = 100 if p >= 25 else 75 if p >= 15 else 45 if p >= 8 else 15
        c["Operative Marge"] = {"label": f"{p:.1f}%", "score": s, "weight": 0.10,
                                "benchmark": "> 15% gut · > 25% exzellent"}
    else:
        c["Operative Marge"] = {"label": "N/A", "score": None, "weight": 0.10,
                                "benchmark": "> 15% gut · > 25% exzellent"}

    # ── FCF-Yield FCF/EV — Value 15% ─────────────────────────────────────
    ev = fund.get("enterprise_value")
    if fcf is not None and ev is not None and ev > 0:
        fy = fcf / ev * 100
        s = 100 if fy >= 6 else 75 if fy >= 4 else 45 if fy >= 2 else 15
        c["FCF-Yield"] = {"label": f"{fy:.1f}%", "score": s, "weight": 0.15,
                          "benchmark": "> 4% attraktiv · > 6% sehr attraktiv"}
    else:
        c["FCF-Yield"] = {"label": "N/A", "score": None, "weight": 0.15,
                          "benchmark": "> 4% attraktiv · > 6% sehr attraktiv"}

    # ── Earnings Yield EBITDA/EV — Value 15% ─────────────────────────────
    ebitda = fund.get("ebitda")
    if ebitda is not None and ev is not None and ev > 0:
        ey = ebitda / ev * 100
        s = 100 if ey >= 8 else 75 if ey >= 5 else 45 if ey >= 3 else 15
        c["Earnings Yield"] = {"label": f"{ey:.1f}%", "score": s, "weight": 0.15,
                               "benchmark": "> 5% attraktiv · > 8% sehr attraktiv (Greenblatt)"}
    else:
        c["Earnings Yield"] = {"label": "N/A", "score": None, "weight": 0.15,
                               "benchmark": "> 5% attraktiv · > 8% sehr attraktiv (Greenblatt)"}

    # ── Net Debt / EBITDA — Safety 8% ────────────────────────────────────
    total_debt = fund.get("total_debt")
    total_cash = fund.get("total_cash")
    if total_debt is not None and ebitda is not None and ebitda > 0:
        net_debt = total_debt - (total_cash or 0)
        ratio = net_debt / ebitda
        s = 100 if ratio <= 0 else 85 if ratio <= 1.0 else 65 if ratio <= 1.5 else 35 if ratio <= 3.0 else 5
        c["Net Debt/EBITDA"] = {"label": f"{ratio:.1f}x", "score": s, "weight": 0.08,
                                "benchmark": "< 1.5x gut · < 0x (Netto-Cash) exzellent · > 3x Red Flag"}
    else:
        c["Net Debt/EBITDA"] = {"label": "N/A", "score": None, "weight": 0.08,
                                "benchmark": "< 1.5x gut · > 3x Red Flag"}

    # ── Zinsdeckung EBIT/Zins — Safety 7% ───────────────────────────────
    ic = fund.get("interest_coverage")
    if ic is not None:
        s = 100 if ic >= 10 else 70 if ic >= 5 else 40 if ic >= 3 else 5
        c["Zinsdeckung"] = {"label": f"{ic:.1f}x", "score": s, "weight": 0.07,
                            "benchmark": "> 10x gut · < 3x Red Flag"}
    elif total_debt is not None and (total_debt or 0) < 1e6:
        c["Zinsdeckung"] = {"label": "Kein Fremdkapital", "score": 100, "weight": 0.07,
                            "benchmark": "> 10x gut · < 3x Red Flag"}
    else:
        c["Zinsdeckung"] = {"label": "N/A", "score": None, "weight": 0.07,
                            "benchmark": "> 10x gut · < 3x Red Flag"}

    # ── 12-1 Momentum — Momentum 10% ─────────────────────────────────────
    mom = tech.get("price_change_1y")
    if mom is not None:
        s = 100 if mom >= 30 else 80 if mom >= 20 else 65 if mom >= 10 else 45 if mom >= 0 else 25 if mom >= -10 else 10
        c["12M-Momentum"] = {"label": f"{mom:+.1f}%", "score": s, "weight": 0.10,
                             "benchmark": "> 10% positiv · > 20% stark"}
    else:
        c["12M-Momentum"] = {"label": "N/A", "score": None, "weight": 0.10,
                             "benchmark": "> 10% positiv · > 20% stark"}

    return _weighted(c)


def short_term_score(fund: dict, tech: dict) -> dict:
    c = {}

    # ── 12-1 Momentum — 25% ──────────────────────────────────────────────
    mom_12 = tech.get("price_change_1y")
    if mom_12 is not None:
        s = 100 if mom_12 >= 30 else 80 if mom_12 >= 20 else 65 if mom_12 >= 10 else 45 if mom_12 >= 0 else 25 if mom_12 >= -10 else 10
        c["12M-Momentum"] = {"label": f"{mom_12:+.1f}%", "score": s, "weight": 0.25,
                             "benchmark": "Top-Dezil = Kaufsignal (Long only)"}
    else:
        c["12M-Momentum"] = {"label": "N/A", "score": None, "weight": 0.25,
                             "benchmark": "Top-Dezil = Kaufsignal"}

    # ── 6-1 Momentum — 15% ───────────────────────────────────────────────
    mom_6 = tech.get("price_change_6m")
    if mom_6 is not None:
        s = 100 if mom_6 >= 20 else 75 if mom_6 >= 10 else 55 if mom_6 >= 0 else 30 if mom_6 >= -10 else 10
        c["6M-Momentum"] = {"label": f"{mom_6:+.1f}%", "score": s, "weight": 0.15,
                            "benchmark": "> 0% positiv · > 10% stark · beschleunigend ideal"}
    else:
        c["6M-Momentum"] = {"label": "N/A", "score": None, "weight": 0.15,
                            "benchmark": "> 0% positiv · > 10% stark"}

    # Earnings Revisions (20%) + Surprise (10%) → nicht via yfinance verfügbar
    # → werden durch Re-Normalisierung herausgerechnet

    # ── RSI — Technicals 10% ─────────────────────────────────────────────
    rsi = tech.get("rsi")
    if rsi is not None:
        s = 100 if rsi < 30 else 65 if rsi < 50 else 35 if rsi < 70 else 15
        c["RSI (14)"] = {"label": f"{rsi:.1f}", "score": s, "weight": 0.10,
                         "benchmark": "< 30 = Reversal-Chance · > 70 = Vorsicht"}
    else:
        c["RSI (14)"] = {"label": "N/A", "score": None, "weight": 0.10,
                         "benchmark": "< 30 = überverkauft · > 70 = überkauft"}

    # ── Kurs vs MA — Technicals 10% ──────────────────────────────────────
    price = tech.get("current_price")
    ma50 = tech.get("ma50")
    ma200 = tech.get("ma200")
    if price and ma200:
        above_both = ma50 is not None and price > ma50 and price > ma200
        above_200 = price > ma200
        s = 100 if above_both else 60 if above_200 else 20
        label = "Über MA50+MA200" if above_both else ("Über MA200" if above_200 else "Unter MA200")
        c["Kurs vs MA"] = {"label": label, "score": s, "weight": 0.10,
                           "benchmark": "Über MA200 = Trend intakt · Golden Cross = bullish"}
    else:
        c["Kurs vs MA"] = {"label": "N/A", "score": None, "weight": 0.10,
                           "benchmark": "Über MA200 = Trend intakt"}

    # ── Short-Term Reversal 1M — Mean-Reversion 10% ───────────────────
    mom_1m = tech.get("price_change_1m")
    if mom_1m is not None:
        s = 100 if mom_1m < -20 else 70 if mom_1m < -10 else 40 if mom_1m < 0 else 20
        c["1M-Reversal"] = {"label": f"{mom_1m:+.1f}%", "score": s, "weight": 0.10,
                            "benchmark": "Starker 1M-Verlust in Qualitätsfirma = Mean-Reversion-Chance"}
    else:
        c["1M-Reversal"] = {"label": "N/A", "score": None, "weight": 0.10,
                            "benchmark": "Extremer 1M-Verlust = potenzielle Reversal-Chance"}

    return _weighted(c)
