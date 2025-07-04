# @role: Exit signal based on On-Balance Volume (OBV) divergence
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, obv, volume
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def obv_exit_filter(df, symbol: str = "") -> tuple[bool, str]:
    if "obv" not in df.columns or len(df["obv"]) < 2:
        return False, "OBV data insufficient for comparison"

    current = df["obv"].iloc[-1]
    previous = df["obv"].iloc[-2]
    logger.info(f"[EXIT-OBV] {symbol} | OBV current={current}, previous={previous}")

    if current < previous:
        return True, f"Falling OBV: {current} < {previous}"
    return False, f"OBV stable or rising: {current} ≥ {previous}"
