# @role: MACD and signal line calculation
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: utility
# @tags: indicator, macd, trend
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def calculate_macd(df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, symbol: str = "") -> pd.DataFrame:
    """
    Calculate MACD, Signal Line, and Histogram.

    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA of MACD Line
    Histogram = MACD Line - Signal Line
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for MACD")

    df['EMA_Fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['EMA_Slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    logger.info(f"[MACD] {symbol} | MACD={df['MACD'].iloc[-1]:.2f}, Signal={df['MACD_Signal'].iloc[-1]:.2f}")
    return df
