# @role: Exit logic based on RSI drops from overbought zone
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, rsi, momentum
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def rsi_exit_filter(df,  rsi_exit_threshold: int = 70, symbol: str = "") -> tuple[bool, str]:
    if "RSI" in df.columns:
        rsi = df["RSI"].iloc[-1]
        price_now = df["close"].iloc[-1]
        price_prev = df["close"].iloc[-2]
        logger.info(f"[EXIT-RSI] {symbol} | RSI={rsi:.2f}, Price Now={price_now:.2f}, Price Prev={price_prev:.2f}")
        if rsi > rsi_exit_threshold and df["close"].iloc[-1] < df["close"].iloc[-2]:
            return True, f"RSI > {rsi_exit_threshold} with price drop"
    return False, ""