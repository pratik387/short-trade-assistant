import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
import pandas as pd
import json
from datetime import datetime, timedelta, time as dt_time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from brokers.kite.kite_broker import KiteBroker
from config.filters_setup import load_filters
from config.logging_config import get_loggers
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from util.cache_meta import load_cache_meta, update_cache_meta
from util.util import is_trading_day

logger, _ = get_loggers()

_meta_lock = threading.Lock()

def ensure_cache_dir(cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

def cache_path(symbol, interval, cache_dir):
    symbol_dir = Path(cache_dir) / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    return str(symbol_dir / f"{symbol}_{interval}.feather")

def get_expected_last_candle_time() -> datetime:
    now = datetime.now()

    # Market hasn't opened yet today
    if now.time() < dt_time(hour=9, minute=15):
        current_date = now.date() - timedelta(days=1)
        while not is_trading_day(current_date):
            current_date -= timedelta(days=1)
        return datetime.combine(current_date, dt_time(hour=15, minute=15))

    # During market hours: calculate latest 1D candle time
    expected = now.replace(hour=15, minute=15, second=0, microsecond=0)

    # Ensure we’re not expecting future candles during early hours on non-trading days
    while not is_trading_day(expected.date()):
        expected -= timedelta(days=1)
        expected = expected.replace(hour=15, minute=15)

    return expected

def update_cache_meta(cache_dir: str, symbol: str, last_updated: datetime):
    meta_path = os.path.join(cache_dir, "cache_meta.json")
    with _meta_lock:
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
            except json.JSONDecodeError:
                meta = {}
        else:
            meta = {}

        meta[symbol] = str(last_updated)

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

def load_cache_meta(cache_dir: str):
    meta_path = os.path.join(cache_dir, "cache_meta.json")
    if not os.path.exists(meta_path):
        return {}

    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Corrupted cache_meta.json at {meta_path}: {e}. Reinitializing.")
        return {}

def fetch_and_update(symbol, broker, config, interval, lookback_days, cache_dir) -> Optional[pd.DataFrame]:
    path = cache_path(symbol, interval, cache_dir)
    cache_meta = load_cache_meta(cache_dir)
    expected_date = get_expected_last_candle_time().date()

    if symbol in cache_meta:
        last_cached = pd.to_datetime(cache_meta[symbol]).date()
        if last_cached >= expected_date:
            logger.info(f"⏩ Skipping {symbol}: already cached for {last_cached}")
            try:
                return pd.read_feather(path).set_index("date")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read cached feather for {symbol}. Rebuilding... ({e})")

    try:
        df_old = pd.read_feather(path) if os.path.exists(path) else pd.DataFrame()
    except Exception as e:
        logger.warning(f"⚠️ Failed to read existing feather file for {symbol}. Treating as empty. ({e})")
        df_old = pd.DataFrame()

    if not df_old.empty:
        df_old["date"] = pd.to_datetime(df_old["date"]).dt.tz_localize(None)

    try:
        df_new = broker.fetch_candles(
            symbol=symbol,
            interval=interval,
            from_date=datetime.now() - timedelta(days=lookback_days * 2),
            to_date=datetime.now().replace(hour=15, minute=30)
        )
        if df_new is None or df_new.empty:
            return

        df_new.reset_index(inplace=True)
        df_new["date"] = pd.to_datetime(df_new["date"]).dt.tz_localize(None)
        df = pd.concat([df_old, df_new]).drop_duplicates(subset="date").sort_values(by="date")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.set_index("date", inplace=True)

        last_date = df.index.max()
        valid_days = []
        while len(valid_days) < lookback_days:
            if is_trading_day(last_date):
                valid_days.append(last_date)
            last_date -= timedelta(days=1)

        min_date = min(valid_days)
        df = df[df.index >= min_date]

        df = enrich_with_indicators_and_score(df, config)
        df = df.reset_index()
        if "level_0" in df.columns:
            df.drop(columns=["level_0"], inplace=True)

        df.to_feather(path)
        update_cache_meta(cache_dir, symbol, df["date"].max())
        logger.info(f"✅ Cached {symbol} ({len(df)} rows)")
        df.set_index("date", inplace=True)
        return df

    except Exception as e:
        logger.error(f"❌ Error updating {symbol}: {e}")
        return

def preload_daily_cache(symbols: List[dict], broker, config, interval, lookback_days, cache_dir):
    cached_data = {}
    filtered_symbols = []
    lock = threading.Lock()

    def worker(symbol_obj):
        symbol = symbol_obj.get("symbol")
        df = fetch_and_update(symbol, broker, config, interval, lookback_days, cache_dir)
        if df is not None and not df.empty:
            with lock:
                cached_data[symbol] = df
                filtered_symbols.append(symbol_obj)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, item) for item in symbols]
        for future in as_completed(futures):
            _ = future.result()

    return filtered_symbols, cached_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="all")
    parser.add_argument("--interval", default="day")
    parser.add_argument("--lookback_days", type=int, default=150)
    parser.add_argument("--cache_dir", default="backend/swing/swing_ohlcv_cache")
    args = parser.parse_args()

    logger.info("🗂 Starting OHLCV cache builder")
    ensure_cache_dir(args.cache_dir)

    config = load_filters(mode="swing")
    broker = KiteBroker()
    symbols = broker.get_symbols(args.index)

    preload_daily_cache(
        symbols=symbols,
        broker=broker,
        config=config,
        interval=args.interval,
        lookback_days=args.lookback_days,
        cache_dir=args.cache_dir
    )

    logger.info("✅ Cache update complete.")
