import logging
from typing import List
import threading
import time
from brokers.kite.kite_broker import KiteBroker
from services.swing.levels import compute_levels_swing
from services.swing.planner import plan_trade
from services.swing.ranker import rank_candidates

logger = logging.getLogger("agent")

rate_limit_lock = threading.Lock()
last_api_call_time = [0]
API_MIN_INTERVAL = 0.35

def _rate_limit():
    with rate_limit_lock:
        elapsed = time.time() - last_api_call_time[0]
        if elapsed < API_MIN_INTERVAL:
            time.sleep(API_MIN_INTERVAL - elapsed)
        last_api_call_time[0] = time.time()

def rate_limited_fetch(symbol, broker, interval, lookback_days):
    _rate_limit()
    return broker.fetch_candles(
        symbol, interval, lookback_days
    )

def screen_and_rank_swing_candidates(suggestions: List[dict], broker: KiteBroker, config: dict, top_n: int = 10) -> List[dict]:
    if not suggestions:
        logger.warning("No suggestions passed to swing screener")
        return []

    enriched = []
    for suggestion in suggestions:
        try:
            symbol = suggestion["symbol"]
            candles = rate_limited_fetch(symbol, broker, interval="day", lookback_days=30)
            if candles is None or candles.empty:
                logger.info(f"⛔️ Skipping {symbol}: empty OHLCV data")
                continue

            # 🔍 Level confirmation
            levels = compute_levels_swing(candles)
            if not levels:
                logger.info(f"⚠️ {symbol}: no levels found")
                continue

            # 🧠 Build plan
            plan = plan_trade(candles, symbol)
            if not plan or plan.get("stop") == 0:
                logger.info(f"⚠️ {symbol}: plan not ready")
                continue

            suggestion["plan"] = plan
            enriched.append(suggestion)

        except Exception as e:
            logger.warning(f"❌ Failed to enrich {suggestion.get('symbol')}: {e}")

    if not enriched:
        logger.info("No swing candidates passed enrichment checks")
        return []

    # 🏆 Final sort
    ranked = rank_candidates(enriched)
    return ranked[:top_n]
