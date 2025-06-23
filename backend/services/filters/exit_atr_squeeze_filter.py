# @role: Detects low volatility ATR squeeze for early exit trigger
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, atr, volatility
import logging
logger = logging.getLogger(__name__)

def atr_squeeze_filter(df, atr_squeeze_threshold: float = 0.01, symbol: str = "") -> tuple[bool, str]:
    if "ATR" not in df.columns:
        return False, ""
    atr_range = df["ATR"].iloc[-1] / df["close"].iloc[-1]
    logger.info(f"[EXIT-ATR] {symbol} | ATR Range={atr_range:.4f} vs threshold={atr_squeeze_threshold}")
    if atr_range < atr_squeeze_threshold:
        return True, "ATR squeeze detected"
    return False, ""