# @role: Exit logic using Bollinger Band breakout or squeeze
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, bollinger, range
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def bollinger_exit_filter(df, bb_exit_threshold: float = 0.9, symbol: str = "") -> tuple[bool, str]:
    if "BB_%B" not in df.columns:
        return False, "Missing BB_%B column"

    val = df["BB_%B"].iloc[-1]
    logger.info(f"[EXIT-BB] {symbol} | %B={val:.2f} vs threshold={bb_exit_threshold}")

    if val > bb_exit_threshold:
        return True, f"%B={val:.2f} > threshold={bb_exit_threshold} — near upper Bollinger Band"
    return False, f"%B={val:.2f} ≤ threshold={bb_exit_threshold} — within safe zone"
