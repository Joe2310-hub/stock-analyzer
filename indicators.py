import pandas as pd
import ta


def calculate_indicators(hist: pd.DataFrame) -> dict:
    close = hist["Close"].squeeze()
    result = {}

    n = len(close)

    # RSI
    if n >= 15:
        try:
            rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi()
            val = rsi_series.iloc[-1]
            result["rsi"] = round(float(val), 1) if pd.notna(val) else None
            result["rsi_series"] = rsi_series
        except Exception:
            result["rsi"] = None

    # MACD
    if n >= 35:
        try:
            macd_obj = ta.trend.MACD(close=close)
            macd_line = macd_obj.macd()
            signal_line = macd_obj.macd_signal()
            macd_hist = macd_obj.macd_diff()
            hist_val = macd_hist.iloc[-1]
            result["macd_histogram"] = float(hist_val) if pd.notna(hist_val) else None
            result["macd_trend"] = "Bullish" if (result["macd_histogram"] or 0) > 0 else "Bearish"
            result["macd_series"] = macd_line
            result["signal_series"] = signal_line
            result["macd_hist_series"] = macd_hist
        except Exception:
            result["macd_trend"] = None

    # Moving Averages
    current_price = float(close.iloc[-1])
    result["current_price"] = current_price

    if n >= 50:
        ma50 = close.rolling(window=50).mean()
        val = ma50.iloc[-1]
        result["ma50"] = round(float(val), 2) if pd.notna(val) else None
        result["ma50_series"] = ma50

    if n >= 200:
        ma200 = close.rolling(window=200).mean()
        val = ma200.iloc[-1]
        result["ma200"] = round(float(val), 2) if pd.notna(val) else None
        result["ma200_series"] = ma200
        if result["ma200"]:
            result["price_vs_ma200"] = round(
                (current_price - result["ma200"]) / result["ma200"] * 100, 1
            )

    # Golden / Death Cross
    if result.get("ma50") and result.get("ma200"):
        result["cross_signal"] = (
            "Golden Cross" if result["ma50"] > result["ma200"] else "Death Cross"
        )

    # Performance
    if n >= 2:
        result["price_change_1d"] = round(
            (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2
        )
    if n >= 22:
        result["price_change_1m"] = round(
            (close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100, 2
        )
    if n >= 126:
        result["price_change_6m"] = round(
            (close.iloc[-1] - close.iloc[-126]) / close.iloc[-126] * 100, 2
        )
    if n >= 2:
        result["price_change_1y"] = round(
            (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100, 2
        )

    return result
