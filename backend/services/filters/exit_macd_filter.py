# @role: Exit rule based on MACD signal crossovers
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, macd, momentum
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def macd_exit_filter(df, fallback=True, symbol: str = ""):
    macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
    macd_signal = df["MACD_Signal"].iloc[-1] if "MACD_Signal" in df.columns else None
    if None in (macd, macd_signal):
        return fallback, "Missing MACD or Signal"
    logger.info(f"[EXIT-MACD] {symbol} | MACD={macd:.2f}, Signal={macd_signal:.2f}")
    reason = f"MACD={macd:.2f}, Signal={macd_signal:.2f}"
    condition = macd < macd_signal
    if condition:
        reason = f"MACD crossover down ({reason})"
    return condition, reason