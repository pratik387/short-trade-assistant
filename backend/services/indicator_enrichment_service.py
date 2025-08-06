import pandas as pd
from pandas_ta import rsi, adx, obv, atr, stoch, cdl_pattern
from services.technical_analysis import calculate_score
import numpy as np

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

        # ✅ Flatten breakdown to a single merged dict
        merged = {}
        if isinstance(breakdown, list):
            for item in breakdown:
                if item.get("weight", 0) != 0:
                    merged[item["filter"]] = item.get("details", {})
        breakdowns.append(merged)

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

def calculate_short_term_adx(df: pd.DataFrame, window: int = 5, smoothing: int = 3) -> pd.Series:
    high = df['high']
    low = df['low']
    close = df['close']

    plus_dm = high.diff()
    minus_dm = low.diff()

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = np.max([tr1, tr2, tr3], axis=0)

    atr = pd.Series(tr).rolling(window).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window).sum() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(window).sum() / atr
    adx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    return pd.Series(adx).rolling(smoothing).mean()

def compute_intraday_breakout_score(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()

    # VWAP (manual for few candles)
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    df['vwap'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

    # RSI slope (short-term)
    df['RSI'] = df['close'].pct_change().rolling(3).mean() * 100
    df['rsi_slope'] = df['RSI'].diff().rolling(3).mean()

    # ADX via utility
    df['ADX_5'] = calculate_short_term_adx(df)
    df['adx_slope'] = df['ADX_5'].diff().rolling(3).mean()

    # Volume surge (short-term)
    df['volume_avg_5'] = df['volume'].rolling(5).mean()
    df['volume_ratio'] = df['volume'] / df['volume_avg_5']

    # Candle info
    df['is_green'] = (df['close'] > df['open']).astype(int)
    df['above_vwap'] = (df['close'] > df['vwap']).astype(int)

    # Range position (short-term)
    high_5 = df['high'].rolling(5).max()
    low_5 = df['low'].rolling(5).min()
    bb_width = (high_5 - low_5).replace(0, np.nan)
    df['range_position'] = (df['close'] - low_5) / bb_width

    # Use dedicated intraday filter config
    filters = config["intraday_filters"]
    hard_filters = config["intraday_hard_filters"]

    score = (
        filters["volume_ratio"]["weight"] * (df['volume_ratio'] > filters["volume_ratio"]["min"]).astype(float) +
        filters["above_vwap"]["weight"] * df['above_vwap'] +
        filters["green_candle"]["weight"] * df['is_green'] +
        filters["adx_slope"]["weight"] * ((df['ADX_5'] > filters["adx_slope"]["min_adx"]) & (df['adx_slope'] > 0)).astype(float) +
        filters["rsi_slope"]["weight"] * (df['rsi_slope'] > 0).astype(float) +
        filters["range_position"]["weight"] * df['range_position'].fillna(0)
    )

    df['breakout_score'] = score

    # Optional hard checks for future use in screener (not scored)
    df['passes_min_breakout'] = df['breakout_score'] >= hard_filters["min_breakout_score"]
    df['passes_volume_ratio'] = df['volume_ratio'] >= hard_filters["min_volume_ratio"]
    # df['passes_top_wick'] = ((df['high'] - df['close']) / (df['high'] - df['low'] + 1e-6)) <= hard_filters["max_top_wick_ratio"]
    # df['passes_green_candle'] = ~hard_filters["require_green_candle"] | (df['is_green'] == 1)
    # df['passes_all_green'] = ~hard_filters["require_all_green_candles"] | (
    #     df['is_green'].rolling(3).sum() == 3
    # )
    # df['passes_higher_highs'] = ~hard_filters["require_higher_highs"] | (
    #     df['high'].diff().rolling(2).apply(lambda x: x.iloc[1] > 0 and x.iloc[0] > 0 if len(x.dropna()) == 2 else False, raw=False).fillna(False).astype(bool)
    # )

    df['passes_all_hard_filters'] = (
        df['passes_min_breakout'] &
        df['passes_volume_ratio'] 
        # &
        # df['passes_top_wick'] &
        # df['passes_green_candle'] &
        # df['passes_all_green'] &
        # df['passes_higher_highs']
    )

    for i, row in df.iterrows():
        reasons = []
        if not row['passes_min_breakout']: reasons.append("low_score")
        if not row['passes_volume_ratio']: reasons.append("volume")
        # if not row['passes_top_wick']: reasons.append("top_wick")
        # if not row['passes_green_candle']: reasons.append("not_green")
        # if not row['passes_all_green']: reasons.append("not_all_green")
        # if not row['passes_higher_highs']: reasons.append("no_higher_highs")
        if reasons:
            logger.info(f"❌ {row.name} rejected: {', '.join(reasons)}")
            
        else:
            logger.info(f"✅ {row.name} passed all checks")

    return df




