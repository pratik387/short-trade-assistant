# @role: Exit rule based on ADX strength and trend direction
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, adx, trend
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()
# Exit ADX Filter
def adx_exit_filter(df, threshold: int = 30, fallback=True, symbol: str = ""):
    adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
    if adx is None:
        return fallback, "ADX not available"
    logger.info(f"[EXIT-ADX] {symbol} | ADX={adx:.2f} vs threshold={threshold}")
    condition = adx < threshold
    reason = f"ADX below threshold (ADX={adx:.2f}, Threshold={threshold})"
    return condition, reason