from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def score_drop_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("score_drop_filter")
    if not filter_cfg.get("enabled", False):
        return []

    threshold = filter_cfg.get("threshold_percent", 40)
    weight = filter_cfg.get("weight", 10)
    reasons = []
    entry_score = kwargs.get("entry_score")
    current_score = kwargs.get("current_score")
    drop = ((entry_score - current_score) / entry_score) * 100 if entry_score else 0
    logger.info(f"[EXIT-SCORE-DROP] {symbol} | Entry={entry_score}, Now={current_score}, Drop={drop:.2f}%")

    if drop >= threshold:
        reasons.append({
            "filter": "score_drop_filter",
            "weight": weight,
            "reason": f"Score dropped by {drop:.1f}% (from {entry_score} to {current_score})",
            "triggered": True
        })
    else:
        reasons.append({
            "filter": "score_drop_filter",
            "weight": 0,
            "reason": f"Score drop {drop:.1f}% < threshold {threshold}%",
            "triggered": False
        })

    return reasons