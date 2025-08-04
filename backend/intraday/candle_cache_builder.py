import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
import time
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
from typing import List, Optional
from brokers.kite.kite_broker import KiteBroker
from config.filters_setup import load_filters
from config.logging_config import get_loggers
from util.util import is_trading_day
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from util.cache_meta import load_cache_meta, update_cache_meta

logger, _ = get_loggers()

# === CONFIG ===
INDEX = "all"  # or your custom index set
INTERVAL = "15minute"
LOOKBACK_DAYS = 6  # in trading days
CACHE_DIR = "backend/intraday/intraday_ohlcv_cache"
RATE_LIMIT_DELAY = 0.35  # seconds


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def cache_path(symbol):
    return os.path.join(CACHE_DIR, f"{symbol}_{INTERVAL}.feather")


def get_expected_last_candle_time() -> datetime:
    now = datetime.now()

    # Market hasn't opened yet today
    if now.time() < dt_time(hour=9, minute=15):
        current_date = now.date() - timedelta(days=1)
        while not is_trading_day(current_date):
            current_date -= timedelta(days=1)
        return datetime.combine(current_date, dt_time(hour=15, minute=15))

    # During market hours: calculate latest 15-min candle boundary
    minutes = (now.minute // 15) * 15
    expected = now.replace(minute=minutes, second=0, microsecond=0)

    # Ensure we’re not expecting future candles during early hours on non-trading days
    while not is_trading_day(expected.date()):
        expected -= timedelta(days=1)
        expected = expected.replace(hour=15, minute=15)

    return expected



def fetch_and_update(symbol, broker, config) -> Optional[pd.DataFrame]:
    path = cache_path(symbol)
    expected_last_candle_time = get_expected_last_candle_time()
    cache_meta = load_cache_meta(CACHE_DIR)

    if symbol in cache_meta:
        last_cached = pd.to_datetime(cache_meta[symbol])
        if last_cached >= expected_last_candle_time:
            logger.info(f"⏩ Skipping {symbol}: already has last candle {last_cached}")
            return pd.read_feather(path).set_index("date")

    # Step 1: Load existing data
    if os.path.exists(path):
        df_old = pd.read_feather(path)
        df_old['date'] = pd.to_datetime(df_old['date']).dt.tz_localize(None)
        last_timestamp = df_old['date'].max() - timedelta(minutes=15)
    else:
        df_old = pd.DataFrame()
        last_timestamp = datetime.now() - timedelta(days=LOOKBACK_DAYS * 2)

    if last_timestamp >= datetime.now():
        logger.warning(f"⏩ Skipping {symbol}: computed from_date is in the future or too recent")
        return

    df_new = None
    to_date = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)

    # Step 2: Fetch new candles
    try:
        df_new = broker.fetch_candles(
            symbol=symbol,
            interval=INTERVAL,
            from_date=last_timestamp,
            to_date=to_date
        )
    except Exception as e:
        logger.error(f"❌ Error fetching data {symbol}: {e}")

    try:
        if df_new is not None and not df_new.empty:
            df_new.reset_index(inplace=True)
            df_new['date'] = pd.to_datetime(df_new['date']).dt.tz_localize(None)
            df = pd.concat([df_old, df_new]).drop_duplicates(subset='date').sort_values(by='date')
            df.set_index('date', inplace=True)
            df = df.between_time("09:15", "15:30")

            # Step 3: Trim to last N trading days
            last_date = df.index.max()
            valid_days = []
            while len(valid_days) < LOOKBACK_DAYS:
                if is_trading_day(last_date):
                    valid_days.append(last_date)
                last_date -= timedelta(days=1)

            min_date = min(valid_days)
            df = df[df.index >= min_date]
            df = enrich_with_indicators_and_score(df, config)

            # Step 4: Save
            df = df.reset_index()
            if "level_0" in df.columns:
                df.drop(columns=["level_0"], inplace=True)
            df.to_feather(path)
            update_cache_meta(CACHE_DIR, symbol, df["date"].max())
            logger.info(f"✅ Updated: {symbol} ({len(df_new)} new candles, {len(df)} kept)")
            df.set_index("date", inplace=True)
            df.index = pd.to_datetime(df.index)
            return df

    except Exception as e:
        logger.error(f"❌ Error updating {symbol}: {e}")


def preload_intraday_cache(symbols: List[str], broker, config):
    cached_data = {}
    filtered_symbols = []

    for symbol_obj in symbols:
        symbol = symbol_obj.get("symbol")
        df = fetch_and_update(symbol, broker, config)

        if df is not None and not df.empty:
            cached_data[symbol] = df
            filtered_symbols.append(symbol_obj)
    return filtered_symbols, cached_data


if __name__ == "__main__":
    logger.info("📦 Starting candle cache builder (smart update mode)")

    ensure_cache_dir()
    config = load_filters(mode="intraday")
    broker = KiteBroker()
    symbols = broker.get_symbols(INDEX)

    for item in symbols:
        symbol = item["symbol"]
        fetch_and_update(symbol, broker, config)
        time.sleep(RATE_LIMIT_DELAY)

    logger.info("✅ Candle cache update complete.")
