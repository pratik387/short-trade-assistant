import pandas as pd

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high = df['high']
    low = df['low']
    close = df['close']

    if isinstance(high, pd.DataFrame):
        high = high.squeeze("columns")
    if isinstance(low, pd.DataFrame):
        low = low.squeeze("columns")
    if isinstance(close, pd.DataFrame):
        close = close.squeeze("columns")

    plus_dm = high.diff()
    minus_dm = low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, min_periods=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, min_periods=period, adjust=False).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(span=period, min_periods=period, adjust=False).mean()

    return pd.DataFrame({
        'ADX_14': adx,
        'DMP_14': plus_di,
        'DMN_14': minus_di
    }, index=close.index)
