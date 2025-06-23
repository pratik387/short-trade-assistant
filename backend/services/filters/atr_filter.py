# @role: Calculates Average True Range (ATR) for volatility
# @used_by: technical_analysis.py
# @filter_type: logic
# @tags: indicator, atr, volatility
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def calculate_atr(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    df = df.copy()
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean().fillna(0)
    logger.info(f"[ATR] {symbol} | ATR={df['atr'].iloc[-1]:.2f}")
    return df[['atr']]