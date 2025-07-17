# @role: Exit signal based on On-Balance Volume (OBV) divergence
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, obv, volume
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def obv_exit_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("obv_exit_filter")
    if not filter_cfg.get("enabled", False):
        return []

    lookback = filter_cfg.get("lookback_days", 5)
    min_drop_pct = filter_cfg.get("min_drop_pct", 1.5)
    weight = filter_cfg.get("weight", 3)

    reasons = []
    
    if "OBV" in df.columns and len(df) >= lookback:
        obv_now = df["OBV"].iloc[-1]
        obv_prev = df["OBV"].iloc[-lookback]

        drop_pct = ((obv_prev - obv_now) / obv_prev) * 100 if obv_prev != 0 else 0

        logger.info(f"[EXIT-OBV] {symbol} | OBV Now={obv_now:.0f}, OBV {lookback}d Ago={obv_prev:.0f}, Drop={drop_pct:.2f}%")

        if drop_pct >= min_drop_pct:
            reasons.append({
                "filter": "obv_exit_filter",
                "weight": weight,
                "reason": f"Falling OBV: {obv_now:.0f} < {obv_prev:.0f} (Drop={drop_pct:.2f}%)",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "obv_exit_filter",
                "weight": 0,
                "reason": f"OBV stable: drop {drop_pct:.2f}% < threshold {min_drop_pct}%",
                "triggered": False
            })

    return reasons