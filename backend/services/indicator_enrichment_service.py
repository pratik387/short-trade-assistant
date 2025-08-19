import pandas as pd
from pandas_ta import rsi, adx, obv, atr, stoch, cdl_pattern
from services.technical_analysis import calculate_score
import numpy as np
import json
from scipy.stats import linregress

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
                    return col.replace("CDL_", "")
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

        # Flatten breakdown list into a dict of filter -> details
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

def calculate_slope(series: pd.Series, window: int = 3) -> pd.Series:
    return series.rolling(window).apply(
        lambda x: linregress(range(len(x)), x).slope if x.notna().all() else np.nan,
        raw=False
    )

# -------------------------------------------------------
# Intraday metrics (Wilder-14, closed bars, no hard gates)
# -------------------------------------------------------
def _drop_forming_last_bar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the last row if it is likely the still-forming 5‑min candle."""
    try:
        ts = pd.to_datetime(df.iloc[-1]["date"] if "date" in df.columns else df.index[-1])
        # consider a bar "closed" if it's <= now-5min
        if ts > pd.Timestamp.now(tz=ts.tz) - pd.Timedelta(minutes=5):
            return df.iloc[:-1].copy()
    except Exception:
        pass
    return df

def compute_intraday_breakout_score(df: pd.DataFrame, config: dict, symbol: str = None, mode: str = 'normal') -> pd.DataFrame:
    """
    Returns a dataframe enriched with intraday features on CLOSED 5-min bars:
      - VWAP
      - RSI(14) Wilder (RMA)
      - ADX(14) (Wilder)
      - simple slopes for RSI/ADX over last 3 bars
      - short-term volume metrics
      - above_vwap / green-candle streak
    No pass/fail flags here — gating is done in the screener.
    """
    df = df.copy()
    if df is None or df.empty:
        return df

    # Use closed bars only — drop only if sufficient candles
    if len(df) > 4:
        df = _drop_forming_last_bar(df)

    # VWAP
    try:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
    except Exception:
        df["vwap"] = np.nan

    # Wilder settings (match Kite/TV defaults)
    params = config.get("intraday_params")
    rsi_len = int(params.get("rsi_len"))
    adx_len = int(params.get("adx_len"))

    # RSI(14) Wilder via pandas_ta (mamode='rma')
    try:
        if len(df) >= rsi_len:
            df["RSI"] = rsi(df["close"], length=rsi_len)
        else:
            df["RSI"] = np.nan
    except Exception as e:
        logger.warning(f"[RSI intraday] failed: {e}")
        df["RSI"] = np.nan

    # ADX 14 and 7 fallback
    def compute_adx_safe(df, length):
        try:
            if len(df) >= length:
                adx_df = adx(df["high"], df["low"], df["close"], length=length, mamode="rma")
                return adx_df[f"ADX_{length}"], adx_df[f"DMP_{length}"], adx_df[f"DMN_{length}"]
            else:
                return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)
        except Exception:
            return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)

    # Primary ADX_14
    df[f"ADX_{adx_len}"], df[f"DMP_{adx_len}"], df[f"DMN_{adx_len}"] = compute_adx_safe(df, adx_len)
    # Backup ADX_7
    df["ADX_7"], df["DMP_7"], df["DMN_7"] = compute_adx_safe(df, 7)

    # ADX_ACTIVE → fallback to ADX_7 if ADX_14 not available
    df["ADX_ACTIVE"] = df[f"ADX_{adx_len}"].combine_first(df["ADX_7"])


    # Slopes (simple, transparent)
    def simple_slope(s: pd.Series, win: int = 3) -> pd.Series:
        try:
            return (s - s.shift(win)) / win
        except Exception:
            return pd.Series(index=s.index, dtype=float)

    df["rsi_slope"] = simple_slope(df["RSI"], win=3)
    df["adx_slope"] = simple_slope(df["ADX_ACTIVE"], win=3)

    # Volume surge (short-term)
    try:
        df["volume_avg_5"] = df["volume"].rolling(5).mean()
        df["volume_ratio"] = df["volume"] / df["volume_avg_5"]
    except Exception:
        df["volume_ratio"] = np.nan

    # Candle info
    try:
        df["is_green"] = (df["close"] > df["open"]).astype(int)
        df["above_vwap"] = (df["close"] > df["vwap"]).astype(int)
        df["is_green_rolling_sum_3"] = df["is_green"].rolling(3).sum()
    except Exception:
        df["above_vwap"] = 0
        df["is_green_rolling_sum_3"] = np.nan
        
    # SQUEEZE (BB width & rolling percentile)
    try:
        bb_win = int(config.get("squeeze", {}).get("window", 20))
        rank_win = int(config.get("squeeze", {}).get("rank_window", 30))
        ma = df["close"].rolling(bb_win, min_periods=bb_win).mean()
        sd = df["close"].rolling(bb_win, min_periods=bb_win).std()
        df["bb_width"] = (4.0 * sd) / ma

        def _pct_rank_last(x):
            sx = pd.Series(x)
            return float(sx.rank(pct=True).iloc[-1] * 100.0)

        minp = max(bb_win, min(rank_win, len(df)))
        df["squeeze_pctile"] = df["bb_width"].rolling(rank_win, min_periods=minp).apply(_pct_rank_last, raw=False)

        good_pct = float(config.get("squeeze", {}).get("good_pctile_max", 70))
        df["squeeze_ok"] = (df["squeeze_pctile"] <= good_pct).astype("Int64")
    except Exception:
        df["bb_width"] = np.nan
        df["squeeze_pctile"] = np.nan
        df["squeeze_ok"] = pd.NA

    return df
