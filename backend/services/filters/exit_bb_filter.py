# @role: Exit logic using Bollinger Band breakout or squeeze
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, bollinger, range
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def bb_exit_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("bb_exit_filter")
    if not filter_cfg.get("enabled", False):
        return []

    threshold = filter_cfg.get("threshold", 0.9)
    weight = filter_cfg.get("weight", 3)

    bbp = df["BB_%B"].iloc[-1] if "BB_%B" in df.columns else None
    reasons = []

    if bbp is not None:
        logger.info(f"[EXIT-BB] {symbol} | %B={bbp:.2f}, Threshold={threshold:.2f}")
        if bbp >= threshold:
            reasons.append({
                "filter": "bb_exit_filter",
                "weight": weight,
                "reason": f"%B={bbp:.2f} > threshold={threshold:.2f} — near upper Bollinger Band",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "bb_exit_filter",
                "weight": 0,
                "reason": f"%B below threshold: {bbp:.2f} < {threshold:.2f}",
                "triggered": False
            })

    return reasons

