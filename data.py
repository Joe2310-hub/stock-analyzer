import math
import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


BASE_URL = "https://financialmodelingprep.com/stable"


def _finite(val):
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _get(endpoint: str, params: dict = None):
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise ValueError("FMP_API_KEY nicht gesetzt.")
    p = {"apikey": api_key}
    if params:
        p.update(params)
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=p, timeout=15)
    if resp.status_code == 429:
        raise ValueError("API Rate Limit erreicht. Bitte später versuchen.")
    if resp.status_code in (402, 403):
        return []
    if resp.status_code != 200:
        raise ValueError(f"API Fehler {resp.status_code} für /{endpoint}")
    return resp.json()


def get_stock_data(ticker_symbol: str) -> dict:
    symbol = ticker_symbol.upper()

    profile_raw = _get("profile", {"symbol": symbol})
    if not profile_raw:
        raise ValueError(f"Ticker '{symbol}' nicht gefunden.")
    profile = profile_raw[0]

    metrics_raw = _get("key-metrics", {"symbol": symbol})
    metrics = metrics_raw[0] if metrics_raw else {}

    ratios_raw = _get("ratios", {"symbol": symbol})
    ratios = ratios_raw[0] if ratios_raw else {}

    income_raw = _get("income-statement", {"symbol": symbol, "limit": 2})
    income = income_raw[0] if income_raw else {}
    income_prev = income_raw[1] if len(income_raw) > 1 else {}

    cashflow_raw = _get("cash-flow-statement", {"symbol": symbol, "limit": 1})
    cashflow = cashflow_raw[0] if cashflow_raw else {}

    balance_raw = _get("balance-sheet-statement", {"symbol": symbol, "limit": 1})
    balance = balance_raw[0] if balance_raw else {}

    # Kurshistorie — FMP zuerst, yfinance als Fallback für Micro/Small Caps
    hist_1y = None
    start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    hist_raw = _get("historical-price-eod/full", {"symbol": symbol, "from": start, "to": end})
    hist_list = hist_raw if isinstance(hist_raw, list) else (hist_raw.get("historical", []) if isinstance(hist_raw, dict) else [])

    if hist_list:
        df = pd.DataFrame(hist_list)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                 "close": "Close", "volume": "Volume"})
        hist_1y = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    else:
        # Fallback: yfinance für Kursdaten (zuverlässig für alle Aktien)
        try:
            hist_1y = yf.Ticker(symbol).history(period="1y")
            if hist_1y.empty:
                raise ValueError(f"Keine Kursdaten für '{symbol}' verfügbar.")
        except Exception as e:
            raise ValueError(f"Keine Kursdaten für '{symbol}' verfügbar.") from e

    # News (402 auf Free Tier → leere Liste)
    news_raw = _get("news/stock", {"symbols": symbol, "limit": 5}) or []
    news = []
    for item in (news_raw or [])[:5]:
        pub = item.get("publishedDate", "")
        try:
            pub = datetime.fromisoformat(pub.replace("Z", "+00:00")).strftime("%d.%m.%Y")
        except Exception:
            pub = pub[:10] if pub else ""
        if item.get("title"):
            news.append({"title": item["title"], "publisher": item.get("site", ""), "date": pub})

    # Wachstumsraten
    rev_cur = _finite(income.get("revenue"))
    rev_pre = _finite(income_prev.get("revenue"))
    revenue_growth = ((rev_cur - rev_pre) / abs(rev_pre)) if rev_cur and rev_pre else None

    ni_cur = _finite(income.get("netIncome"))
    ni_pre = _finite(income_prev.get("netIncome"))
    earnings_growth = ((ni_cur - ni_pre) / abs(ni_pre)) if ni_cur and ni_pre and ni_pre != 0 else None

    # 52W aus range-String "195.07-315.37" parsen
    week_52_low, week_52_high = None, None
    rng = profile.get("range", "")
    if rng and "-" in str(rng):
        parts = str(rng).split("-")
        if len(parts) == 2:
            week_52_low = _finite(parts[0])
            week_52_high = _finite(parts[1])

    fundamentals = {
        "company_name": profile.get("companyName", symbol),
        "sector": profile.get("sector", "N/A"),
        "industry": profile.get("industry", "N/A"),
        "current_price": _finite(profile.get("price")),
        "market_cap": _finite(profile.get("marketCap")),
        # Bewertung
        "pe_ratio": _finite(ratios.get("priceToEarningsRatio")),
        "forward_pe": _finite(ratios.get("priceToEarningsRatio")),
        "peg_ratio": _finite(ratios.get("priceToEarningsGrowthRatio")),
        "enterprise_value": _finite(metrics.get("enterpriseValue")),
        # Quality
        "roe": _finite(metrics.get("returnOnEquity")),
        "gross_margin": _finite(ratios.get("grossProfitMargin")),
        "operating_margin": _finite(ratios.get("operatingProfitMargin")),
        "profit_margin": _finite(ratios.get("netProfitMargin")),
        "ebitda": _finite(income.get("ebitda")),
        "ebitda_margin": _finite(ratios.get("ebitdaMargin")),
        # Cash & Earnings
        "free_cash_flow": _finite(cashflow.get("freeCashFlow")),
        "net_income": _finite(income.get("netIncome")),
        "total_revenue": _finite(income.get("revenue")),
        "revenue_growth": _finite(revenue_growth),
        "earnings_growth": _finite(earnings_growth),
        "eps_trailing": _finite(ratios.get("netIncomePerShare")),
        "eps_forward": None,
        # Bilanz
        "total_debt": _finite(balance.get("totalDebt")),
        "total_cash": _finite(balance.get("cashAndCashEquivalents")),
        "debt_to_equity": _finite(ratios.get("debtToEquityRatio")),
        "interest_coverage": _finite(ratios.get("interestCoverageRatio")),
        # Sonstiges
        "week_52_high": week_52_high,
        "week_52_low": week_52_low,
        "dividend_yield": _finite(ratios.get("dividendYield")),
        "beta": _finite(profile.get("beta")),
    }

    return {"fundamentals": fundamentals, "history_1y": hist_1y, "news": news}
