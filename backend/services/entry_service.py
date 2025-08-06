# @role: Manages entry strategy scoring, filtering, and stock selection
# @used_by: suggestion_logic.py
# @filter_type: logic
# @tags: entry, strategy, service
import time
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.technical_analysis import passes_hard_filters
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from exceptions.exceptions import InvalidTokenException, DataUnavailableException
from config.logging_config import get_loggers
from brokers.mock.mock_broker import MockBroker
from util.diagnostic_report_generator import diagnostics_tracker
from jobs.daily_cache_builder import preload_daily_cache
from pytz import timezone
india_tz = timezone("Asia/Kolkata")

logger, trade_logger = get_loggers()

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
        df.index = pd.to_datetime(df.index).tz_localize(None)
        as_of_date = as_of_date.replace(tzinfo=None)
        if len(df) < 1:
            return None

        latest = df.iloc[-1]

        # Load thresholds from config
        MIN_AVG_VOLUME = config.get("min_volume")
        MIN_PRICE = config.get("min_price")
        MAX_PRICE = config.get("max_price")
        MIN_ATR_PCT = config.get("min_atr_pct")
        SOFT_PREFILTER = config.get("enable_soft_prefilter")

        # Prefilter checks
        try:
            atr = latest.get("ATR")
            close = latest.get("close")
            atr_pct = (atr / close) * 100 if atr and close else 0
            avg_vol = df["volume"].rolling(20).mean().iloc[-1] if "volume" in df else 0

            if avg_vol < MIN_AVG_VOLUME:
                reason = f"low_volume={avg_vol:.0f}"
                logger.info(f"[ENTRY SKIP] {symbol} — {reason}")
                if not SOFT_PREFILTER:
                    return None

            elif not (MIN_PRICE <= close <= MAX_PRICE):
                reason = f"price_outside_range=₹{close:.2f}"
                logger.info(f"[ENTRY SKIP] {symbol} — {reason}")
                if not SOFT_PREFILTER:
                    return None

            elif atr_pct < MIN_ATR_PCT:
                reason = f"low_atr_pct={atr_pct:.2f}%"
                logger.info(f"[ENTRY SKIP] {symbol} — {reason}")
                if not SOFT_PREFILTER:
                    return None

        except Exception as e:
            logger.warning(f"[PREFILTER ERROR] {symbol}: {e}")
            if not SOFT_PREFILTER:
                return None

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
        self.weights = config.get("entry_filters")
        self.min_price = config.get("min_price")
        self.min_volume = config.get("min_volume")
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

        filtered_symbols, candle_cache = preload_daily_cache(
            symbols=symbols,
            broker=self.data_provider,
            config=self.config,
            interval="day",
            lookback_days=self.config.get("lookback_days", 180),
            cache_dir="backend/cache/swing_ohlcv_cache"
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
        top_n = suggestions[:30]
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
