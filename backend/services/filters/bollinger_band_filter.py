# @role: Bollinger Band %B calculation for price range positioning
# @used_by: technical_analysis.py
# @filter_type: logic
# @tags: indicator, bollinger, bb
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std_dev: float = 2.0, symbol: str = "") -> pd.DataFrame:
    """
    Calculate Bollinger Bands and %B for a given DataFrame with 'close' prices.

    BB Middle = SMA(n)
    BB Upper = SMA(n) + (k * standard deviation)
    BB Lower = SMA(n) - (k * standard deviation)
    %B = (Price - Lower Band) / (Upper Band - Lower Band)
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for Bollinger Bands")

    sma = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()

    df['BB_Middle'] = sma
    df['BB_Upper'] = sma + (num_std_dev * std)
    df['BB_Lower'] = sma - (num_std_dev * std)
    df['BB_%B'] = (df['close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
    logger.debug(f"[BB] {symbol} | %B={df['BB_%B'].iloc[-1]:.2f}")
    return df

    return df

