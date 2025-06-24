# @role: Checks exit conditions around Fibonacci retracement zones
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, fibonacci, support
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def fibonacci_exit_filter(df, fibonacci_exit_retracement_zone: float=0.99, symbol: str = "") -> tuple[bool, str]:
    if "fibonacci_resistance" not in df.columns or "close" not in df.columns:
        return False, ""
    close = df["close"].iloc[-1]
    resistance = df["fibonacci_resistance"].iloc[-1]
    logger.info(f"[EXIT-FIB] {symbol} | Close={close:.2f} vs Resistance={resistance:.2f} (Zone={fibonacci_exit_retracement_zone})")
    if close >= resistance * fibonacci_exit_retracement_zone:
        return True, "Price near Fibonacci resistance"
    return False, ""