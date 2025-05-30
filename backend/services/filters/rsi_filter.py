import pandas as pd

def calculate_rsi(close_prices: pd.DataFrame, period: int = 14) -> pd.Series:
    # Ensure 1D Series
    if isinstance(close_prices, pd.DataFrame):
        close = close_prices.squeeze("columns")
    else:
        close = close_prices

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return pd.Series(rsi, name="RSI", index=close.index)
