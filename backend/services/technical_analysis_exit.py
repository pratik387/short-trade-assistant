# technical_analysis_exit.py — Computes weighted exit score from various filters
# @used_by: exit_service.py

import pandas as pd
from datetime import datetime
from dateutil.parser import parse
from config.logging_config import get_loggers
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
from services.filters.atr_filter import calculate_atr
from services.filters.rsi_filter import calculate_rsi
from services.filters.bollinger_band_filter import calculate_bollinger_bands
from services.filters.obv_filter import calculate_obv
from services.filters.fibonacci_filter import calculate_fibonacci_levels, is_fibonacci_support_zone

agent_logger, _ = get_loggers()

def prepare_exit_indicators(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("Missing 'close' column for MACD/ADX calculation")
    if len(df) < 15:
        raise ValueError("Insufficient rows for indicator calculation. Need at least 15 candles.")
    df = df.copy()
    try:
        df = calculate_macd(df)
        df = df.join(calculate_adx(df[['high', 'low', 'close']], 30, False))
        df = df.join(calculate_atr(df, symbol))
        df = df.join(calculate_obv(df, symbol=symbol))
        r = calculate_rsi(df[['close']], symbol=symbol)
        df['RSI'] = r['RSI'] if isinstance(r, pd.DataFrame) else r
        df = calculate_bollinger_bands(df, symbol=symbol)
        closes = df["close"].tail(20)
        levels = calculate_fibonacci_levels(closes)
        preferred_level = levels.get("0.5") or levels.get("0.382")  # fallback if 0.5 missing
        if preferred_level:
            df["fibonacci_resistance"] = preferred_level
    except Exception as e:
        agent_logger.warning(f"Indicator calculation failed: {e}")

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
            agent_logger.warning(f"{func.__name__} failed — {e}")
    return df

def apply_exit_filters(df: pd.DataFrame, entry_price: float, entry_time: datetime, current_date:datetime, criteria: dict, fallback_exit: bool, symbol: str = "") -> tuple[bool, list[dict]]:
    reasons = []
    total_score = 0
    threshold = criteria.get("soft_exit_threshold", 6)

    def process_filter(label, condition, weight, reason):
        nonlocal total_score
        if condition:
            total_score += weight
            reasons.append({"filter": label, "weight": weight, "reason": reason})

    adx_exit, adx_reason = adx_exit_filter(df, criteria.get("adx_exit_threshold"), symbol=symbol)
    process_filter("ADX", adx_exit, criteria.get("weight_adx_exit", 0), adx_reason)

    macd_exit, macd_reason = macd_exit_filter(df, symbol=symbol)
    process_filter("MACD", macd_exit, criteria.get("weight_macd_exit", 0), macd_reason)

    rsi_exit, rsi_reason = rsi_exit_filter(df, criteria.get("rsi_exit_threshold"), symbol=symbol)
    process_filter("RSI", rsi_exit, criteria.get("weight_rsi_drop", 0), rsi_reason)

    bb_exit, bb_reason = bollinger_exit_filter(df, criteria.get("bb_exit_threshold"), symbol=symbol)
    process_filter("Bollinger Band", bb_exit, criteria.get("weight_bb_upper_band", 0), bb_reason)

    obv_exit, obv_reason = obv_exit_filter(df, symbol=symbol)
    process_filter("OBV", obv_exit, criteria.get("weight_obv_fall", 0), obv_reason)

    atr_exit, atr_reason = atr_squeeze_filter(df, criteria.get("atr_squeeze_threshold"), symbol=symbol)
    process_filter("ATR Squeeze", atr_exit, criteria.get("weight_atr_squeeze", 0), atr_reason)

    if isinstance(entry_time, str):
        entry_time = parse(entry_time)
    decay_exit, decay_reason = time_decay_filter(entry_price, entry_time, df, current_date, criteria.get("duration_threshold"), criteria.get("pnl_threshold"), symbol=symbol)
    process_filter("Time Decay", decay_exit, criteria.get("weight_time_decay", 0), decay_reason)

    fib_exit, fib_reason = fibonacci_exit_filter(df, criteria.get("fibonacci_exit_retracement_zone"), symbol=symbol)
    process_filter("Fibonacci", fib_exit, criteria.get("weight_fibonacci", 0), fib_reason)

    override_keys = {"use_override_exit", "override_exit_threshold"}
    override_args = {k: v for k, v in criteria.items() if k in override_keys}
    override_exit, override_reason = check_overrides(df, symbol=symbol, **override_args)
    process_filter("Override", override_exit, criteria.get("weight_override", 0), override_reason)

    allow_exit = total_score >= threshold
    return allow_exit, reasons
