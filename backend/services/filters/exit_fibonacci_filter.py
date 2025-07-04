# @role: Checks exit conditions around Fibonacci retracement zones
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, fibonacci, support
from config.logging_config import get_loggers
from services.filters.fibonacci_filter import is_fibonacci_support_zone

logger, trade_logger = get_loggers()

def fibonacci_exit_filter(df, fibonacci_exit_retracement_zone: float = 0.99, symbol: str = "") -> tuple[bool, str]:
    if "fibonacci_resistance" not in df.columns or "close" not in df.columns:
        return False, "Missing required columns for Fibonacci exit"

    close = df["close"].iloc[-1]
    resistance = df["fibonacci_resistance"].iloc[-1]
    logger.info(f"[EXIT-FIB] {symbol} | Close={close:.2f} vs Resistance={resistance:.2f} (Zone={fibonacci_exit_retracement_zone})")

    if close >= resistance * fibonacci_exit_retracement_zone:
        return True, f"Close ₹{close:.2f} ≥ ₹{resistance * fibonacci_exit_retracement_zone:.2f} — near Fibonacci resistance"
    return False, f"Close ₹{close:.2f} < ₹{resistance * fibonacci_exit_retracement_zone:.2f} — below resistance zone"


def fibonacci_support_exit_filter(df, symbol: str = "") -> tuple[bool, str]:
    try:
        levels = df["fibonacci_levels"].iloc[-1] if "fibonacci_levels" in df.columns else {}
        current_price = df["close"].iloc[-1]
        in_support = is_fibonacci_support_zone(current_price, levels, symbol=symbol)
        if in_support:
            return True, f"Price ₹{current_price:.2f} is near Fibonacci support levels: {levels}"
        else:
            return False, f"Price ₹{current_price:.2f} is not near Fibonacci support levels"
    except Exception as e:
        logger.warning(f"is_fibonacci_support_zone failed — {e}")
        return False, f"Error checking Fibonacci support zone: {e}"
