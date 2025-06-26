# @role: Relative Strength Index (RSI) indicator
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: utility
# @tags: indicator, rsi, momentum
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def calculate_rsi(close_prices: pd.DataFrame, period: int = 14,  symbol: str = "") -> pd.Series:
    # Ensure 1D Series
    if isinstance(close_prices, pd.DataFrame):
        close = close_prices.squeeze("columns")
    else:
        close = close_prices

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    logger.debug(f"[RSI] {symbol} | RSI={rsi.iloc[-1]:.2f}")
    return pd.Series(rsi, name="RSI", index=close.index)