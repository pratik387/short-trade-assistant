# @role: Calculates Average True Range (ATR) for volatility
# @used_by: technical_analysis.py
# @filter_type: logic
# @tags: indicator, atr, volatility
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def calculate_atr(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    df = df.copy()
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean().fillna(0)
    logger.debug(f"[ATR] {symbol} | ATR={df['atr'].iloc[-1]:.2f}")
    return df[['atr']]