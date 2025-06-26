# @role: Stochastic oscillator (%K) filter for momentum reversal
# @used_by: technical_analysis.py
# @filter_type: utility
# @tags: indicator, stochastic, oscillator
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def calculate_stochastic(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    df = df.copy()
    low_min = df['low'].rolling(window=14).min()
    high_max = df['high'].rolling(window=14).max()
    df['stochastic_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    df['stochastic_k'] = df['stochastic_k'].fillna(0)
    df['stochastic_d'] = df['stochastic_k'].rolling(window=3).mean().fillna(0)
    logger.debug(f"[STOCHASTIC] {symbol} | %K={df['stochastic_k'].iloc[-1]:.2f} | %D={df['stochastic_d'].iloc[-1]:.2f}")
    return df[['stochastic_k', 'stochastic_d']]