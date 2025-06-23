# @role: Exit logic using Bollinger Band breakout or squeeze
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, bollinger, range
import logging
logger = logging.getLogger(__name__)

def bollinger_exit_filter(df, bb_exit_threshold: float=0.9, symbol: str = "") -> tuple[bool, str]:
    if "BB_%B" in df.columns and df["BB_%B"].iloc[-1] > bb_exit_threshold:
        val = df["BB_%B"].iloc[-1]
        logger.info(f"[EXIT-BB] {symbol} | %B={val:.2f} vs threshold={bb_exit_threshold}")
        return True, "Near upper Bollinger Band"
    return False, ""