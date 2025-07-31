import os
import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from brokers.kite.kite_broker import KiteBroker
from config.filters_setup import load_filters
from services.entry_service import evaluate_symbol
from intraday.ltp_fetcher import fetch_ltp_for_symbols
from config.logging_config import get_loggers
from util.util import is_market_active
from brokers.data.indexes import get_token_for_symbol
from datetime import datetime, timezone
from services.indicator_enrichment_service import enrich_with_indicators_and_score

logger, _ = get_loggers()

CACHE_DIR = "backend/intraday/intraday_ohlcv_cache"
INTERVAL = "15minute"
INDEX = "all"
LOOKBACK_DAYS = 6
RATE_LIMIT_DELAY = 0.35
config = load_filters("intraday")


def load_cached_df(symbol):
    path = os.path.join(CACHE_DIR, f"{symbol}_{INTERVAL}.feather")
    if not os.path.exists(path):
        return None
    df = pd.read_feather(path)
    df.set_index("date", inplace=True)
    df.index = pd.to_datetime(df.index)
    return df


def run_intraday_scoring():
    logger.info("🚀 Starting intraday screener")

    cached_data = {}
    ltp_map = {}
    market_open = is_market_active()
    broker = KiteBroker()
    symbols = [item["symbol"] for item in broker.get_symbols(INDEX)]

    for symbol in symbols:
        df = load_cached_df(symbol)
        if not df.empty:
            cached_data[symbol] = df
        else:
            logger.warning(f"⚠️ No valid candles for {symbol} in cache")

    if market_open:
        ltp_map = fetch_ltp_for_symbols(symbols)
        if symbol in ltp_map:
            ltp = ltp_map[symbol]
            df.iloc[-1, df.columns.get_loc("close")] = ltp
            logger.info(f"💹 Replaced last close with LTP for {symbol}: ₹{ltp}")
    else:
        for symbol, df in cached_data.items():
            ltp = df["close"].iloc[-1]
            ltp_map[symbol] = ltp
            logger.info(f"📦 Using fallback LTP from cache for {symbol}: ₹{ltp}")

    results = []
    for symbol in symbols:
        item = {"symbol": symbol, "instrument_token": get_token_for_symbol(symbol)}
        df = cached_data.get(symbol)
        if df is None:
            continue
        try:
            # Overwrite the final candle's close with live LTP if available
            if symbol in ltp_map:
                df.at[df.index[-1], "close"] = ltp_map[symbol]
            df = enrich_with_indicators_and_score(df, config)
            df.set_index("date", inplace=True)
            result = evaluate_symbol(item, config=config, candle_cache={symbol: df}, as_of_date=datetime.now(timezone.utc))
            if result:
                results.append(result)
        except Exception as e:
            logger.warning(f"⚠️ Failed to evaluate {symbol}: {e}")

    results.sort(key=lambda x: (-x.get("score", 0), -x.get("adx", 0)))
    suggestions = results[:15]

    logger.info(f"✅ Got {len(suggestions)} intraday suggestions")
    for s in suggestions:
        print(f"{s['symbol']} | Score: {s['score']} | LTP: ₹{s['close']} | Filters: {s['breakdown']}")


if __name__ == "__main__":
    run_intraday_scoring()
