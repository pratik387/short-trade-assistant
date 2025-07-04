# @role: Override mechanism to force exit decisions irrespective of filters
# @used_by: technical_analysis_exit.py
# @filter_type: exit
# @tags: exit, override, manual
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def check_overrides(df, ma_short=20, ma_long=50, rsi_lower=50, symbol: str = "") -> tuple[bool, str]:
    short_ma = df["close"].rolling(ma_short).mean().iloc[-1]
    long_ma = df["close"].rolling(ma_long).mean().iloc[-1]
    rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else None

    logger.info(f"[EXIT-OVERRIDE] {symbol} | MA Short={short_ma:.2f}, MA Long={long_ma:.2f}, RSI={rsi if rsi else 'NA'}")

    if short_ma < long_ma:
        return True, f"MA crossover down: {short_ma:.2f} < {long_ma:.2f}"

    if rsi is not None and rsi < rsi_lower:
        return True, f"RSI dropped below {rsi_lower} (current: {rsi:.2f})"

    return False, f"MA ok ({short_ma:.2f} ≥ {long_ma:.2f}), RSI ok ({rsi:.2f})" if rsi is not None else "RSI not available"
