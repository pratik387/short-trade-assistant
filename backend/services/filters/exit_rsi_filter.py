# @role: Exit logic based on RSI drops from overbought zone
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, rsi, momentum
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

import logging
logger = logging.getLogger(__name__)

def rsi_exit_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("rsi_drop_filter")
    if not filter_cfg.get("enabled", False):
        return []

    weight = filter_cfg.get("weight", 3)
    upper = filter_cfg.get("rsi_upper", 70)
    lower = filter_cfg.get("rsi_lower", 45)

    rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else None
    close = df["close"].iloc[-1] if "close" in df.columns else None
    prev_close = df["close"].iloc[-2] if "close" in df.columns and len(df) >= 2 else None
    reasons = []

    if rsi is not None:
        if rsi > upper:
            if close is not None and prev_close is not None and close < prev_close:
                logger.info(f"[EXIT-RSI] {symbol} | RSI={rsi:.2f}, Price Now={close:.2f}, Price Prev={prev_close:.2f}")
                reasons.append({
                    "filter": "rsi_exit_filter",
                    "weight": weight,
                    "reason": f"RSI overbought and price dropped: RSI={rsi:.2f}, Close={close} < Prev={prev_close}",
                    "triggered": True
                })
            else:
                logger.info(f"[EXIT-RSI] {symbol} | RSI={rsi:.2f} > {upper}, no price drop")
                reasons.append({
                    "filter": "rsi_exit_filter",
                    "weight": 0,
                    "reason": f"RSI in overbought zone but no price drop: RSI={rsi:.2f}",
                    "triggered": False
                })
        elif rsi < lower:
            logger.info(f"[EXIT-RSI] {symbol} | RSI={rsi:.2f} < {lower}")
            reasons.append({
                "filter": "rsi_exit_filter",
                "weight": weight,
                "reason": f"RSI fell below lower bound: {rsi:.2f} < {lower}",
                "triggered": True
            })
        else:
            reasons.append({
                "filter": "rsi_exit_filter",
                "weight": 0,
                "reason": f"RSI in normal range: {rsi:.2f}",
                "triggered": False
            })

    return reasons