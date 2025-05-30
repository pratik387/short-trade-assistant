import pandas as pd

def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std_dev: float = 2.0) -> pd.DataFrame:
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

    return df
