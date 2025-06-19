import pandas as pd
from datetime import datetime
from services.filters.exit_adx_filter import adx_exit_filter
from services.filters.exit_macd_filter import macd_exit_filter
from services.filters.exit_override_filter import check_overrides
from services.filters.exit_rsi_filter import rsi_exit_filter
from services.filters.exit_bb_filter import bollinger_exit_filter
from services.filters.exit_obv_filter import obv_exit_filter
from services.filters.exit_atr_squeeze_filter import atr_squeeze_filter
from services.filters.exit_time_decay_filter import time_decay_filter
from services.filters.exit_fibonacci_filter import fibonacci_exit_filter
from services.filters.adx_filter import calculate_adx
from services.filters.macd_filter import calculate_macd

def prepare_exit_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("Missing 'close' column for MACD/ADX calculation")
    if len(df) < 15:
        raise ValueError("Insufficient rows for indicator calculation. Need at least 15 candles.")
    df = df.copy()
    try:
        df = calculate_macd(df)
        df = df.join(calculate_adx(df[['high', 'low', 'close']], 30, False))
    except Exception as e:
        print(f"Indicator calculation failed: {e}")

    for func in [
        rsi_exit_filter,
        bollinger_exit_filter,
        obv_exit_filter,
        atr_squeeze_filter,
        fibonacci_exit_filter
    ]:
        try:
            func(df)
        except Exception as e:
            print(f"Warning: {func.__name__} failed — {e}")
    return df

def apply_exit_filters(df: pd.DataFrame, entry_price: float, entry_time: datetime, criteria: dict, fallback_exit: bool) -> tuple[bool, list[str]]:
    reasons = []
    total_score = 0
    threshold = criteria.get("soft_exit_threshold", 4)

    adx_exit, adx_reason = adx_exit_filter(df)
    if adx_exit:
        total_score += criteria.get("'weight_adx_exit'", 0)
        reasons.append(adx_reason)

    macd_exit, macd_reason = macd_exit_filter(df)
    if macd_exit:
        total_score += criteria.get("weight_macd_exit", 0)
        reasons.append(macd_reason)

    rsi_exit, rsi_reason = rsi_exit_filter(df)
    if rsi_exit:
        total_score += criteria.get("weight_rsi_drop", 0)
        reasons.append(rsi_reason)

    bb_exit, bb_reason = bollinger_exit_filter(df)
    if bb_exit:
        total_score += criteria.get("weight_bb_upper_band", 0)
        reasons.append(bb_reason)

    obv_exit, obv_reason = obv_exit_filter(df)
    if obv_exit:
        total_score += criteria.get("weight_obv_fall", 0)
        reasons.append(obv_reason)

    atr_exit, atr_reason = atr_squeeze_filter(df)
    if atr_exit:
        total_score += criteria.get("weight_atr_squeeze", 0)
        reasons.append(atr_reason)

    from dateutil.parser import parse
    if isinstance(entry_time, str):
        entry_time = parse(entry_time)
    decay_exit, decay_reason = time_decay_filter(entry_price, entry_time, df)
    if decay_exit:
        total_score += criteria.get("weight_time_decay", 0)
        reasons.append(decay_reason)

    fib_exit, fib_reason = fibonacci_exit_filter(df)
    if fib_exit:
        total_score += criteria.get("weight_fibonacci", 0)
        reasons.append(fib_reason)

    override_keys = {"use_override_exit", "override_exit_threshold"}
    override_args = {k: v for k, v in criteria.items() if k in override_keys}
    override_exit, override_reason = check_overrides(df, **override_args)
    if override_exit:
        total_score += criteria.get("weight_override", 0)
        reasons.append(f"Override: {override_reason}")

    allow_exit = total_score >= threshold
    return allow_exit, reasons
