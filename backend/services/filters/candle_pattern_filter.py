# @role: Detects bullish candlestick patterns like hammer, engulfing etc.
# @used_by: project_map.py
# @filter_type: utility
# @tags: filter, candle, pattern
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def is_bullish_engulfing(df: pd.DataFrame, symbol: str = "") -> bool:
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    result = (prev['close'] < prev['open'] and curr['close'] > curr['open'] and curr['close'] > prev['open'] and curr['open'] < prev['close'])
    logger.debug(f"[ENGULFING] {symbol} | Result={'✅' if result else '❌'}")
    return result

def is_hammer(df: pd.DataFrame, symbol: str = "") -> bool:
    if len(df) < 1:
        return False
    candle = df.iloc[-1]
    body = abs(candle['close'] - candle['open'])
    lower_wick = candle['open'] - candle['low'] if candle['open'] > candle['close'] else candle['close'] - candle['low']
    upper_wick = candle['high'] - max(candle['close'], candle['open'])
    result = lower_wick > 2 * body and upper_wick < body and body > 0
    logger.debug(f"[HAMMER] {symbol} | Result={'✅' if result else '❌'}")
    return result