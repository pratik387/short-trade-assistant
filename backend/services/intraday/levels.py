# services/intraday/levels.py
from datetime import time as dtime
import pandas as pd

# Opening Range: first 15 minutes (India cash: 09:15–09:30)
ORB_START = dtime(9, 15)
ORB_END   = dtime(9, 30)

# Default breakout buffer in percent (0.08%)
DEFAULT_BUFFER_BPCT = 0.08

def opening_range(df_5m: pd.DataFrame) -> tuple[float, float]:
    """
    Returns (orb_high, orb_low) from 09:15–09:30 on a 5m dataframe.
    df_5m must have datetime index or 'date' column and 'high','low'.
    """
    if 'date' in df_5m.columns:
        t = pd.to_datetime(df_5m['date']).dt.time
        win = df_5m[(t >= ORB_START) & (t <= ORB_END)]
    else:
        t = df_5m.index.time
        win = df_5m[(t >= ORB_START) & (t <= ORB_END)]
    if win.empty:
        return float('nan'), float('nan')
    return float(win['high'].max()), float(win['low'].min())

def yesterday_levels(df_daily: pd.DataFrame) -> tuple[float, float]:
    """
    Returns (y_high, y_low) from previous daily bar.
    df_daily must be sorted ascending; last row is latest session.
    """
    if len(df_daily) < 2:
        return float('nan'), float('nan')
    prev = df_daily.iloc[-2]
    return float(prev['high']), float(prev['low'])

def broke_above(level: float, close: float, buffer_bpct: float = DEFAULT_BUFFER_BPCT) -> bool:
    if pd.isna(level) or pd.isna(close):
        return False
    return close > level * (1 + buffer_bpct / 100.0)

def distance_bpct(level: float, price: float) -> float:
    """
    Percentage distance of price from level (positive if above).
    """
    if pd.isna(level) or pd.isna(price) or level == 0:
        return float('nan')
    return (price / level - 1.0) * 100.0
