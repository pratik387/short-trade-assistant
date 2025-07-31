import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta
from brokers.kite.kite_broker import KiteBroker
from config.filters_setup import load_filters
from config.logging_config import get_loggers
from util.util import is_trading_day

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


def fetch_and_update(symbol, broker):
    path = cache_path(symbol)

    # Step 1: Load existing data
    if os.path.exists(path):
        df_old = pd.read_feather(path)
        df_old['date'] = pd.to_datetime(df_old['date'], utc=True)
        last_timestamp = df_old['date'].max() - timedelta(minutes=30)
    else:
        df_old = pd.DataFrame()
        last_timestamp = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS * 2)

    # Defensive check
    if last_timestamp >= datetime.now(timezone.utc):
        logger.warning(f"⏩ Skipping {symbol}: computed from_date is in the future or too recent")
        return

    # Step 2: Fetch new candles
    try:
        df_new = broker.fetch_candles(
            symbol=symbol,
            interval=INTERVAL,
            from_date=last_timestamp,
            to_date=datetime.now(timezone.utc)
        )
    except Exception as e:
        logger.error(f"❌ Error fetching data {symbol}: {e}")

    try:
        
        if df_new is not None and not df_new.empty:
            df_new.reset_index(inplace=True)
            df_new['date'] = pd.to_datetime(df_new['date'], utc=True)
            df = pd.concat([df_old, df_new]).drop_duplicates(subset='date').sort_values(by='date')
            df.set_index('date', inplace=True)

            # ⏳ Filter only valid Indian market hours (09:15–15:30 IST → 03:45–10:00 UTC)
            df = df.between_time("03:45", "10:00")

            # Step 3: Trim to last N trading days
            last_date = df.index.max()
            valid_days = []
            while len(valid_days) < LOOKBACK_DAYS:
                if is_trading_day(last_date):
                    valid_days.append(last_date)
                last_date -= timedelta(days=1)

            min_date = min(valid_days)
            df = df[df.index >= min_date]

            # Step 4: Save
            df.reset_index().to_feather(path)
            logger.info(f"✅ Updated: {symbol} ({len(df_new)} new candles, {len(df)} kept)")

    except Exception as e:
        logger.error(f"❌ Error updating {symbol}: {e}")

if __name__ == "__main__":
    logger.info("📦 Starting candle cache builder (smart update mode)")

    ensure_cache_dir()
    config = load_filters(mode="intraday")
    broker = KiteBroker()
    symbols = broker.get_symbols(INDEX)

    for item in symbols:
        symbol = item["symbol"]
        fetch_and_update(symbol, broker)
        time.sleep(RATE_LIMIT_DELAY)

    logger.info("✅ Candle cache update complete.")
