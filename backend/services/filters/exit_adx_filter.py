# @role: Exit rule based on ADX strength and trend direction
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, adx, trend
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()
# Exit ADX Filter
def adx_exit_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("adx_exit_filter")
    if not filter_cfg.get("enabled", False):
        return []

    threshold = filter_cfg.get("threshold", 35)
    weight = filter_cfg.get("weight", 3)

    adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
    reasons = []

    if adx is not None:
        logger.info(f"[EXIT-ADX] {symbol} | ADX={adx:.2f}, Threshold={threshold:.2f}")
        if adx < threshold:
            reasons.append({
                "filter": "adx_exit_filter",
                "weight": weight,
                "reason": f"ADX dropped below threshold: {adx:.2f} < {threshold}",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "adx_exit_filter",
                "weight": 0,
                "reason": f"ADX above threshold: {adx:.2f} >= {threshold}",
                "triggered": False
            })

    return reasons