from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def fibonacci_support_exit_filter(df, config, symbol, **kwargs):
    if config is None or "fibonacci_support_exit_filter" not in config:
        return []

    cfg = config["fibonacci_support_exit_filter"]
    if not cfg.get("enabled", False):
        return []

    buffer_pct = cfg.get("buffer_pct", 0.005)  # 0.5%
    weight = cfg.get("weight")

    try:
        price = df["close"].iloc[-1]
        fib = df["FIBONACCI_LEVELS"].iloc[-1]
        if not isinstance(fib, dict):
            return []

        # Trigger if price is close to any major support level
        for level_name in ["0.5", "0.618", "0.786"]:
            support = fib.get(level_name)
            if support and (abs(price - support) / support) <= buffer_pct:
                return [{
                    "filter": "fibonacci_support_exit_filter",
                    "weight": weight,
                    "reason": f"Price near Fib support {level_name}={support:.2f}",
                    "triggered": True
                }]
    except Exception as e:
        print(f"[EXIT-FIBSUP] {symbol} | Error: {e}")

    return []
