# @role: Calculates On-Balance Volume (OBV) for volume trend
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: utility
# @tags: indicator, obv, volume
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def calculate_obv(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    df = df.copy()
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i - 1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['obv'] = obv
    logger.debug(f"[OBV] {symbol} | OBV={df['obv'].iloc[-1]}")
    return df[['obv']]