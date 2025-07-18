# @role: Manages entry strategy scoring, filtering, and stock selection
# @used_by: suggestion_logic.py
# @filter_type: logic
# @tags: entry, strategy, service
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from services.technical_analysis import passes_hard_filters, calculate_score
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from exceptions.exceptions import InvalidTokenException, DataUnavailableException
from config.logging_config import get_loggers
from brokers.mock.mock_broker import MockBroker
from util.diagnostic_report_generator import diagnostics_tracker
from pytz import timezone
india_tz = timezone("Asia/Kolkata")

logger, trade_logger = get_loggers()

def preload_and_filter_symbols(symbols, data_provider, config, min_price, min_volume, as_of_date):
    candle_cache = {}
    filtered_symbols = []
    lock = threading.Lock()

    def load_symbol(item):
        symbol = item.get("symbol")
        try:
            from_date = as_of_date - timedelta(days=config.get("lookback_days", 180))
            df = data_provider.fetch_candles(
                symbol=symbol,
                interval=config.get("interval", "day"),
                from_date=from_date,
                to_date=as_of_date
            )
            
            if df is None or df.empty:
                return

            latest = df.iloc[-1]
            if latest["close"] <= min_price or latest["volume"] < min_volume:
                return

            with lock:
                candle_cache[symbol] = df
                filtered_symbols.append(item)
        except Exception:
            logger.exception("Error preloading or filtering %s", symbol)

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(load_symbol, item): item for item in symbols}
        for future in as_completed(futures):
            try:
                future.result()  # will raise if load_symbol errored
            except Exception as e:
                logger.error(f"Exception in preload thread: {e}")


    return filtered_symbols, candle_cache

def evaluate_symbol(item, config, candle_cache, as_of_date):
    symbol = item.get("symbol")
    symbol_start = time.perf_counter()
    try:
        df = candle_cache.get(symbol)
        if df is None or df.empty:
            return None
        
        #usually for live treading and get single stock suggestion
        if "RSI" not in df.columns or "ADX_14" not in df.columns:
            df = enrich_with_indicators_and_score(df, config=config)
            df.set_index("date", inplace=True)
        df = df[df.index <= as_of_date]
        if len(df) < 1:
            return None

        latest = df.iloc[-1]
        if not passes_hard_filters(latest, config, symbol=symbol):
            logger.debug("%s did not pass hard filters, skipping", symbol)
            return None

        score = latest.get("ENTRY_SCORE")
        breakdown = latest.get("ENTRY_BREAKDOWN", [])
        logger.info(f"Scored {symbol}: {score:.2f} | Breakdown: {breakdown}")

        elapsed_ms = (time.perf_counter() - symbol_start) * 1000
        logger.debug("Processed %s in %.1fms, score=%.2f", symbol, elapsed_ms, score)

        return {
            "symbol": symbol,
            "instrument_token": item.get("instrument_token"),
            "adx": round(float(latest["ADX_14"]), 2),
            "dmp": round(float(latest["DMP_14"]), 2),
            "dmn": round(float(latest["DMN_14"]), 2),
            "rsi": round(float(latest["RSI"]), 2),
            "macd": round(float(latest["MACD"]), 2),
            "macd_signal": round(float(latest["MACD_SIGNAL"]), 2),
            "bb": round(float(latest.get("BB_%B", 0)), 2),
            "stochastic_k": round(float(latest.get("STOCHASTIC_K", 0)), 2),
            "obv": round(float(latest.get("OBV", 0)), 2),
            "atr": round(float(latest.get("ATR", 0)), 2),
            "stop_loss": round(latest["close"] * 0.97, 2),
            "score": float(score) if score is not None else 0.0,
            "breakdown": breakdown,
            "close": round(float(latest["close"]), 2),
            "volume": int(latest["volume"]),
        }

    except InvalidTokenException:
        logger.error("Token expired while processing %s — aborting suggestions", symbol)
        raise
    except DataUnavailableException:
        logger.exception("Symbol not available: %s", symbol)
        return None
    except Exception as e:
        logger.exception("Error processing symbol %s", symbol + f": {e}")
        return None

class EntryService:
    def __init__(self, data_provider, config: dict, index: str = "nifty_50"):
        self.data_provider = data_provider
        self.config = config
        self.weights = config.get("score_weights", {})
        self.min_price = config.get("min_price", 50)
        self.min_volume = config.get("min_volume", 100_000)
        self.index = index

        # Auto-adjust thread count for real brokers to avoid API throttling
        if isinstance(data_provider, MockBroker):
            self.max_workers = 20
        else:
            self.max_workers = 1

    def get_suggestions(self, as_of_date: datetime = None) -> list:
        if as_of_date is None:
            as_of_date = datetime.now(india_tz)
        logger.info(
            "Starting get_suggestions (min_price=%s, min_volume=%s)",
            self.min_price, self.min_volume
        )
        start_all = time.perf_counter()

        suggestions = []
        symbols = self.data_provider.get_symbols(self.index) or []
        logger.debug("Fetched %d symbols to evaluate", len(symbols))

        # Preload candle data and filter early (multithreaded)
        filtered_symbols, candle_cache = preload_and_filter_symbols(
            symbols, self.data_provider, self.config, self.min_price, self.min_volume, as_of_date=as_of_date
        )

        logger.info("Preloaded and filtered %d symbols", len(filtered_symbols))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {
                executor.submit(
                    evaluate_symbol, item, self.config, candle_cache, as_of_date
                ): item for item in filtered_symbols
            }
            for future in as_completed(future_to_symbol):
                result = future.result()
                if result:
                    suggestions.append(result)

        suggestions.sort(key=self.tie_breaker)
        top_n = suggestions[:12]
        total_time = (time.perf_counter() - start_all)
        logger.info(
            "Completed get_suggestions: %d out of %d symbols, returned %d suggestions in %.2fs",
            len(suggestions), len(filtered_symbols), len(top_n), total_time
        )

        return top_n

    # Smarter sorting with tie-breakers
    def tie_breaker(self, x):
        return (
            -x.get("score", 0),                      # 1. Higher score
            -x.get("adx", 0),                     # 2. Stronger trend
            abs(x.get("rsi", 50) - 50),              # 3. RSI closest to neutral
            -x.get("volume", 0),                     # 4. Optional: Higher volume
        )

    def execute_entry(self, suggestion: dict, quantity: int, timestamp, entry_price):
        symbol = suggestion["symbol"]
        score = suggestion["score"]
        breakdown = suggestion["breakdown"]
        indicators = {k: v for k, v in suggestion.items() if k in ["adx", "dmp", "dmn", "rsi", "macd", "macd_signal", "bb", "stochastic_k", "obv", "atr"]}

        self.data_provider.place_order(symbol=symbol, quantity=quantity, action="buy", timestamp=timestamp)
        diagnostics_tracker.record_entry(
            symbol=symbol,
            entry_time=timestamp,
            entry_price=entry_price,
            score=score,
            filters=breakdown,
            indicators=indicators
        )
