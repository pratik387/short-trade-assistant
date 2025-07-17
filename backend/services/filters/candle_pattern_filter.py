from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

BULLISH_PATTERNS = [
    "CDL_BULLISH_ENGULFING",
    "CDL_HAMMER",
    "CDL_PIERCING",
    "CDL_MORNINGSTAR",
    "CDL_THREE_WHITE_SOLDIERS"
]

def bullish_candle_pattern_filter(df, symbol: str = "") -> bool:
    if df is None or df.empty or "CANDLE_PATTERN" not in df.columns:
        logger.warning(f"[CANDLE-FILTER] {symbol} | DataFrame missing or pattern column not found.")
        return False

    try:
        pattern = df["CANDLE_PATTERN"].iloc[-1]
        result = pattern in BULLISH_PATTERNS
        logger.debug(f"[CANDLE-FILTER] {symbol} | Pattern={pattern} | Bullish Match={'✅' if result else '❌'}")
        return result
    except Exception as e:
        logger.warning(f"[CANDLE-FILTER] {symbol} | Error: {e}")
        return False
