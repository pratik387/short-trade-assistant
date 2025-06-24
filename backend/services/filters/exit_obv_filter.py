# @role: Exit signal based on On-Balance Volume (OBV) divergence
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, obv, volume
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def obv_exit_filter(df, symbol: str = "") -> tuple[bool, str]:
    if "obv" in df.columns:
        current, previous = df["obv"].iloc[-1], df["obv"].iloc[-2]
        logger.info(f"[EXIT-OBV] {symbol} | OBV current={current}, previous={previous}")
        if current < previous:
            return True, "Falling OBV"
    return False, ""