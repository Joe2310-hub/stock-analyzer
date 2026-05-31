import math
import yfinance as yf
from datetime import datetime


def _finite(val):
    """Return val if it's a finite real number, else None."""
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def get_stock_data(ticker_symbol: str) -> dict:
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        # Try to at least get history to confirm ticker exists
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError(f"Ticker '{ticker_symbol}' nicht gefunden.")

    hist_1y = ticker.history(period="1y")
    if hist_1y.empty:
        raise ValueError(f"Keine Kursdaten für '{ticker_symbol}' verfügbar.")

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None and not hist_1y.empty:
        current_price = float(hist_1y["Close"].iloc[-1])

    fundamentals = {
        "company_name": info.get("longName") or ticker_symbol,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "current_price": current_price,
        "market_cap": _finite(info.get("marketCap")),
        # Bewertung
        "pe_ratio": _finite(info.get("trailingPE")),
        "forward_pe": _finite(info.get("forwardPE")),
        "peg_ratio": _finite(info.get("pegRatio")),
        "enterprise_value": _finite(info.get("enterpriseValue")),
        # Quality
        "roe": _finite(info.get("returnOnEquity")),
        "gross_margin": _finite(info.get("grossMargins")),
        "operating_margin": _finite(info.get("operatingMargins")),
        "profit_margin": _finite(info.get("profitMargins")),
        "ebitda": _finite(info.get("ebitda")),
        "ebitda_margin": _finite(info.get("ebitdaMargins")),
        # Cash & Earnings
        "free_cash_flow": _finite(info.get("freeCashflow")),
        "net_income": _finite(info.get("netIncomeToCommon")),
        "total_revenue": _finite(info.get("totalRevenue")),
        "revenue_growth": _finite(info.get("revenueGrowth")),
        "earnings_growth": _finite(info.get("earningsGrowth")),
        "eps_trailing": _finite(info.get("trailingEps")),
        "eps_forward": _finite(info.get("forwardEps")),
        # Bilanz / Safety
        "total_debt": _finite(info.get("totalDebt")),
        "total_cash": _finite(info.get("totalCash")),
        "debt_to_equity": _finite(info.get("debtToEquity")),
        # Sonstiges
        "week_52_high": info.get("fiftyTwoWeekHigh"),
        "week_52_low": info.get("fiftyTwoWeekLow"),
        # Cap at 15% — yfinance occasionally returns corrupt values (e.g. 35% for AAPL)
        "dividend_yield": dy if (dy := info.get("dividendYield")) and dy < 0.15 else None,
        "beta": _finite(info.get("beta")),
    }

    news = []
    try:
        raw_news = ticker.news or []
        for item in raw_news[:5]:
            content = item.get("content", {})
            title = content.get("title") or item.get("title", "")
            publisher = content.get("provider", {}).get("displayName") or item.get("publisher", "")
            pub_time = content.get("pubDate") or ""
            if pub_time:
                try:
                    dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                    pub_time = dt.strftime("%d.%m.%Y")
                except Exception:
                    pub_time = ""
            if title:
                news.append({"title": title, "publisher": publisher, "date": pub_time})
    except Exception:
        pass

    return {
        "fundamentals": fundamentals,
        "history_1y": hist_1y,
        "news": news,
    }
