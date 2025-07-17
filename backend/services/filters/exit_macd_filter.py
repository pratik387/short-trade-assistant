# @role: Exit rule based on MACD signal crossovers
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, macd, momentum
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def macd_exit_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("macd_exit_filter")
    if not filter_cfg.get("enabled", False):
        return []

    weight = filter_cfg.get("weight", 3)
    reasons = []

    macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
    signal = df["MACD_SIGNAL"].iloc[-1] if "MACD_SIGNAL" in df.columns else None

    if macd is not None and signal is not None:
        logger.info(f"[EXIT-MACD] {symbol} | MACD={macd:.2f}, Signal={signal:.2f}")
        if macd < signal:
            reasons.append({
                "filter": "macd_exit_filter",
                "weight": weight,
                "reason": f"MACD crossover down: MACD={macd:.2f} < Signal={signal:.2f}",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "macd_exit_filter",
                "weight": 0,
                "reason": f"MACD still above signal: MACD={macd:.2f} >= Signal={signal:.2f}",
                "triggered": False
            })

    return reasons
