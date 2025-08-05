from datetime import datetime, timedelta
import threading
import time
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from brokers.kite.kite_broker import KiteBroker
from config.logging_config import get_loggers
from services.indicator_enrichment_service import compute_intraday_breakout_score

logger, _ = get_loggers()

rate_limit_lock = threading.Lock()
last_api_call_time = [0]
API_MIN_INTERVAL = 0.35
MAX_WORKERS = 5

def rate_limited_fetch(symbol, broker, from_date, to_date):
    with rate_limit_lock:
        elapsed = time.time() - last_api_call_time[0]
        if elapsed < API_MIN_INTERVAL:
            time.sleep(API_MIN_INTERVAL - elapsed)
        last_api_call_time[0] = time.time()
    return broker.fetch_candles(symbol=symbol, interval="5minute", from_date=from_date, to_date=to_date)


def intraday_filter_passed(symbol: str, broker, config) -> bool:
    try:
        market_open = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        now = datetime.now().replace(second=0, microsecond=0)

        if now < market_open:
            logger.info("⚠️ Market not open yet — skipping intraday filter")
            return False

        to_date = now - timedelta(minutes=5)
        from_date = to_date - timedelta(minutes=20)

        df = rate_limited_fetch(symbol, broker, from_date, to_date)
        if df is None or df.empty or len(df) < 3:
            logger.info(f"⚠️ Not enough candles to screen {symbol}")
            return False

        df = compute_intraday_breakout_score(df, config)
        last = df.iloc[-1]

        if not last.get("passes_all_hard_filters", False):
            logger.debug(f"❌ {symbol} rejected: {last.get('debug_reasons', 'unspecified')}")
            return False

        logger.info(f"✅ {symbol} passed intraday filter with score {last['breakout_score']:.2f}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ Intraday check failed for {symbol}: {e}")
        return False


def screen_intraday_candidates(suggestions: List[dict], broker: KiteBroker, config) -> List[dict]:
    logger.info("🔍 Running intraday screener with threading")
    passed = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(intraday_filter_passed, s["symbol"], broker, config): s for s in suggestions
        }
        for future in as_completed(futures):
            symbol_obj = futures[future]
            if future.result():
                passed.append(symbol_obj)

    logger.info(f"✅ {len(passed)}/{len(suggestions)} passed intraday filter")
    return passed