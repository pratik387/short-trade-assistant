# @role: Exit override based on multiple weakening signals
# @tags: exit, override, fail-safe

from config.logging_config import get_loggers

logger, _ = get_loggers()

BEARISH_PATTERNS = [
    "CDL_BEARISH_ENGULFING",
    "CDL_DARKCLOUDCOVER",
    "CDL_EVENINGSTAR",
    "CDL_SHOOTINGSTAR",
    "CDL_HANGINGMAN",
    "CDL_THREE_BLACK_CROWS"
]


def override_filter(df, config, symbol, **kwargs):
    reasons = []
    if not config.get("multi_signal_weakness").get("enabled", True):
        return reasons

    try:
        macd = df["MACD"].iloc[-1]
        signal = df["MACD_SIGNAL"].iloc[-1]
        rsi = df["RSI"].iloc[-1]
        pattern = df.get("bearish_pattern", "").lower()

        macd_trigger = macd < signal
        rsi_trigger = rsi < config["multi_signal_weakness"].get("rsi_below", 45)
        pattern_trigger = pattern in BEARISH_PATTERNS

        if macd_trigger and rsi_trigger and pattern_trigger:
            reason = (
                f"MACD weakening (MACD={macd:.2f} < Signal={signal:.2f}), "
                f"RSI dropped below {rsi:.2f}, "
                f"Bearish pattern: {pattern}"
            )
            reasons.append({
                "filter": "multi_signal_weakness",
                "weight": config["multi_signal_weakness"].get("weight", 5),
                "reason": reason,
                "triggered": True
            })
            logger.info(f"[EXIT-OVERRIDE] {symbol} | {reason}")

    except Exception as e:
        logger.warning(f"[override_filter] failed for {symbol}: {e}")

    return reasons
