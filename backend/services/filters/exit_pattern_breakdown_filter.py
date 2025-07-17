from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

# Define high-confidence bearish patterns
BEARISH_PATTERNS = [
    "CDL_BEARISH_ENGULFING",
    "CDL_DARKCLOUDCOVER",
    "CDL_EVENINGSTAR",
    "CDL_SHOOTINGSTAR",
    "CDL_HANGINGMAN",
    "CDL_THREE_BLACK_CROWS"
]

def pattern_breakdown_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("pattern_breakdown_filter")
    if not filter_cfg.get("enabled", False):
        return []

    weight = filter_cfg.get("weight", 3)
    reasons = []

    try:
        pattern = df["CANDLE_PATTERN"].iloc[-1] if "CANDLE_PATTERN" in df.columns else ""
        logger.info(f"[EXIT-PATTERN] {symbol} | Pattern={pattern}")

        if pattern in BEARISH_PATTERNS:
            reasons.append({
                "filter": "pattern_breakdown_filter",
                "weight": weight,
                "reason": f"Bearish pattern detected: {pattern}",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "pattern_breakdown_filter",
                "weight": 0,
                "reason": f"No bearish pattern found ({pattern})",
                "triggered": False
            })
    except Exception as e:
        logger.warning(f"[EXIT-PATTERN] {symbol} | Error: {e}")
        reasons.append({
            "filter": "pattern_breakdown_filter",
            "weight": 0,
            "reason": f"Error evaluating pattern: {e}",
            "triggered": False
        })

    return reasons
