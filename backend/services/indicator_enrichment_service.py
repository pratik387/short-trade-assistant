import pandas as pd
from pandas_ta import rsi, adx, obv, atr, stoch, cdl_pattern
from services.technical_analysis import calculate_score

from config.logging_config import get_loggers
logger, trade_logger = get_loggers()

def enrich_with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
    elif isinstance(df.index, pd.DatetimeIndex):
        pass
    else:
        logger.error("DataFrame lacks 'date' column or datetime index")
        raise ValueError("Cannot enrich without a valid datetime index or 'date' column")
    
    df.attrs["missing_indicators"] = []

    try:
        df["RSI"] = rsi(df["close"])
    except Exception as e:
        logger.warning(f"[RSI] failed: {e}")
        df.attrs["missing_indicators"].append("RSI")
        df["RSI"] = None

    try:
        df["EMA_FAST"] = df["close"].ewm(span=12, adjust=False).mean()
        df["EMA_SLOW"] = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = df["EMA_FAST"] - df["EMA_SLOW"]
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]
    except Exception as e:
        logger.warning(f"[MACD] failed: {e}")
        df.attrs["missing_indicators"].append("MACD")
        df["MACD"] = df["MACD_SIGNAL"] = df["MACD_HIST"] = None

    if df.shape[0] < 15:
        logger.warning("⚠️ Skipping enrichment — insufficient candles")
        return df
    try:
        adx_df = adx(df["high"], df["low"], df["close"])
        df["ADX_14"] = adx_df["ADX_14"]
        df["DMP_14"] = adx_df["DMP_14"]
        df["DMN_14"] = adx_df["DMN_14"]
    except Exception as e:
        logger.warning(f"[ADX] failed: {e}")
        df.attrs["missing_indicators"].append("ADX")
        df["ADX_14"] = df["DMP_14"] = df["DMN_14"] = None
    adx_df = adx(df["high"], df["low"], df["close"])

    try:
        df["OBV"] = obv(df["close"], df["volume"])
        df["VOLUME_AVG"] = df["volume"].rolling(20).mean()
    except Exception as e:
        logger.warning(f"[OBV] failed: {e}")
        df.attrs["missing_indicators"].append("OBV")
        df["OBV"] = None

    try:
        df["ATR"] = atr(df["high"], df["low"], df["close"])
    except Exception as e:
        logger.warning(f"[ATR] failed: {e}")
        df.attrs["missing_indicators"].append("ATR")
        df["ATR"] = None
    
    try:
        stoch_df = stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        df["STOCHASTIC_K"] = stoch_df["STOCHk_14_3_3"]
        df["STOCHASTIC_D"] = stoch_df["STOCHd_14_3_3"]
    except Exception as e:
        logger.warning(f"[STOCHASTIC] failed: {e}")
        df.attrs["missing_indicators"].append("STOCHASTIC")
        df["STOCHASTIC_K"] = df["STOCHASTIC_D"] = None

    try:
        df["SMA_50"] = df["close"].rolling(50).mean()
        df["SMA_20"] = df["close"].rolling(20).mean()
        sma = df["SMA_20"]
        std = df["close"].rolling(20).std()
        df["BB_MIDDLE"] = sma
        df["BB_UPPER"] = sma + (2 * std)
        df["BB_LOWER"] = sma - (2 * std)
        df["BB_%B"] = (df["close"] - df["BB_LOWER"]) / (df["BB_UPPER"] - df["BB_LOWER"])
    except Exception as e:
        logger.warning(f"[BOLLINGER] failed: {e}")
        df.attrs["missing_indicators"].append("BOLLINGER")
        df["BB_%B"] = df["BB_UPPER"] = df["BB_LOWER"] = df["BB_MIDDLE"] = None

    try:
        df["AVG_RSI"] = df["RSI"].rolling(14).mean()
    except Exception as e:
        logger.warning(f"[AVG_RSI] failed: {e}")
        df.attrs["missing_indicators"].append("AVG_RSI")
        df["AVG_RSI"] = None

    try:
        window = 30
        fib_data = []
        for i in range(len(df)):
            if i < window:
                fib_data.append({})
                continue
            fib_levels = calculate_fibonacci_levels(df["close"].iloc[i - window:i])
            fib_data.append(fib_levels)

        df["FIBONACCI_LEVELS"] = fib_data
    except Exception as e:
        logger.warning(f"[FIBONACCI] failed: {e}")
        df.attrs["missing_indicators"].append("FIBONACCI")
        df["FIBONACCI_LEVELS"] = [{} for _ in range(len(df))]

    try:
        pattern_df = cdl_pattern(open_=df["open"], high=df["high"], low=df["low"], close=df["close"])
        pattern_df = pattern_df.fillna(0)

        def get_pattern_name(row):
            for col in pattern_df.columns:
                if row[col] != 0:
                    return col.replace("CDL_", "")  # return cleaned pattern name
            return None

        df["CANDLE_PATTERN"] = pattern_df.apply(get_pattern_name, axis=1)
    except Exception as e:
        logger.warning(f"[CANDLE_PATTERN] failed: {e}")
        df.attrs["missing_indicators"].append("CANDLE_PATTERN")
        df["CANDLE_PATTERN"] = None

    df.reset_index(inplace=True)
    return df

def calculate_entry_score(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()
    df.set_index("date", inplace=True)
    scores, breakdowns = [], []
    for i, (index, row) in enumerate(df.iterrows()):
        score, breakdown, extras = calculate_score(row, config, full_df=df.iloc[:i+1])
        scores.append(score)
        breakdowns.append(breakdown if isinstance(breakdown, list) else [])
        for key, val in extras.items():
            if val is not None:
                df.at[row.name, key] = val
    df["ENTRY_SCORE"] = scores
    df["ENTRY_BREAKDOWN"] = breakdowns
    df.reset_index(inplace=True)
    return df

def enrich_with_indicators_and_score(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = enrich_with_indicators(df)
    df = calculate_entry_score(df, config)
    return df

def calculate_fibonacci_levels(series: pd.Series) -> dict:
    """
    Given a price series (usually 20-day close), calculate key Fibonacci retracement levels.
    Returns a dictionary with levels: 0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0
    """
    if series.empty or len(series) < 2:
        return {}

    high = series.max()
    low = series.min()
    diff = high - low

    return {
        "0.0": round(high, 2),
        "0.236": round(high - 0.236 * diff, 2),
        "0.382": round(high - 0.382 * diff, 2),
        "0.5": round(high - 0.5 * diff, 2),
        "0.618": round(high - 0.618 * diff, 2),
        "0.786": round(high - 0.786 * diff, 2),
        "1.0": round(low, 2)
    }
