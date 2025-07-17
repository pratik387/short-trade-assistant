# @role: Detects low volatility ATR squeeze for early exit trigger
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, atr, volatility
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def atr_squeeze_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("atr_squeeze_filter")
    if not filter_cfg.get("enabled", False):
        return []

    weight = filter_cfg.get("weight", 3)
    threshold = filter_cfg.get("threshold", 0.01)
    reasons = []

    if "ATR" in df.columns and len(df) >= 2:
        atr_now = df["ATR"].iloc[-1]
        atr_prev = df["ATR"].iloc[-2]
        if atr_prev > 0:
            contraction = abs(atr_now - atr_prev) / atr_prev
            logger.info(f"[EXIT-ATR-SQUEEZE] {symbol} | ATR Now={atr_now:.2f}, Prev={atr_prev:.2f}, Change={contraction:.2%}")
            if contraction < threshold:
                reasons.append({
                    "filter": "atr_squeeze_filter",
                    "weight": weight,
                    "reason": f"ATR squeeze detected: change={contraction:.2%} < threshold={threshold:.2%}",
                    "triggered": True
                })
            else:
                reasons.append({
                    "filter": "atr_squeeze_filter",
                    "weight": 0,
                    "reason": f"ATR change normal: {contraction:.2%} >= {threshold:.2%}",
                    "triggered": False
                })

    return reasons
