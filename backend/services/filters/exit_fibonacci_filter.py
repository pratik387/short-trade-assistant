# @role: Checks exit conditions around Fibonacci retracement zones
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, fibonacci, support
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def fibonacci_exit_filter(df, config, symbol, **kwargs):
    if config is None or "fibonacci_exit_filter" not in config:
        return []

    cfg = config["fibonacci_exit_filter"]
    if not cfg.get("enabled", False):
        return []

    retracement_zone = str(cfg.get("retracement_zone", "0.618"))
    buffer_pct = cfg.get("buffer_pct")  # 0.5%
    weight = cfg.get("weight", 3)

    try:
        price = df["close"].iloc[-1]
        fib = df["FIBONACCI_LEVELS"].iloc[-1]
        if not isinstance(fib, dict):
            return []

        level = fib.get(retracement_zone)
        if not level:
            return []

        # Trigger if price is below resistance
        if price < level * (1 - buffer_pct):
            return [{
                "filter": "fibonacci_exit_filter",
                "weight": weight,
                "reason": f"Price={price:.2f} < Fib({retracement_zone})={level:.2f}",
                "triggered": True
            }]
    except Exception as e:
        print(f"[EXIT-FIB] {symbol} | Error: {e}")

    return []
