# @role: Detects low volatility ATR squeeze for early exit trigger
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, atr, volatility
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def atr_squeeze_filter(df, atr_squeeze_threshold: float = 0.01, symbol: str = "") -> tuple[bool, str]:
    if "atr" not in df.columns or "close" not in df.columns:
        return False, "ATR or close price data missing"

    atr = df["atr"].iloc[-1]
    close = df["close"].iloc[-1]
    atr_range = atr / close
    logger.info(f"[EXIT-ATR] {symbol} | ATR Range={atr_range:.4f} vs threshold={atr_squeeze_threshold}")

    if atr_range < atr_squeeze_threshold:
        return True, f"ATR squeeze detected | ATR={atr:.2f}, Close={close:.2f}, Ratio={atr_range:.4f}"
    return False, f"No ATR squeeze | ATR={atr:.2f}, Close={close:.2f}, Ratio={atr_range:.4f}"
