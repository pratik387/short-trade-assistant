# @role: Manages entry strategy scoring, filtering, and stock selection
# @used_by: suggestion_logic.py
# @filter_type: logic
# @tags: entry, strategy, service
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.technical_analysis import passes_hard_filters, prepare_indicators, calculate_score
from exceptions.exceptions import InvalidTokenException, DataUnavailableException
from config.logging_config import get_loggers
from brokers.mock.mock_broker import MockBroker
from util.diagnostic_report_generator import diagnostics_tracker

logger, trade_logger = get_loggers()

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
            self.max_workers = 3

    def get_suggestions(self) -> list:
        logger.info(
            "Starting get_suggestions (min_price=%s, min_volume=%s)",
            self.min_price, self.min_volume
        )
        start_all = time.perf_counter()

        suggestions = []
        symbols = self.data_provider.get_symbols(self.index) or []
        logger.debug("Fetched %d symbols to evaluate", len(symbols))

        def evaluate_symbol(item):
            symbol = item.get("symbol")
            symbol_start = time.perf_counter()
            try:
                df = self.data_provider.fetch_candles(
                    symbol=symbol,
                    interval=self.config.get("interval", "day"),
                    days=self.config.get("lookback_days", 180)
                )
                if df is None or df.empty:
                    logger.debug("No data for %s, skipping", symbol)
                    return None

                df = prepare_indicators(df, symbol=symbol)
                latest = df.iloc[-1]

                if latest["close"] <= self.min_price:
                    logger.debug("%s: close %s <= min_price %s, skipping", symbol, latest["close"], self.min_price)
                    return None
                if latest["volume"] < self.min_volume:
                    logger.debug("%s: volume %s < min_volume %s, skipping", symbol, latest["volume"], self.min_volume)
                    return None

                if not passes_hard_filters(latest, self.config, symbol=symbol):
                    logger.debug("%s did not pass hard filters, skipping", symbol)
                    return None

                avg_rsi = df["RSI"].rolling(14).mean().iloc[-1]
                score, breakdown = calculate_score(latest, self.config, avg_rsi, candle_match=False, symbol=symbol)
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
                    "macd_signal": round(float(latest["MACD_Signal"]), 2),
                    "bb": round(float(latest.get("BB_%B", 0)), 2),
                    "stochastic_k": round(float(latest.get("stochastic_k", 0)), 2),
                    "obv": round(float(latest.get("obv", 0)), 2),
                    "atr": round(float(latest.get("atr", 0)), 2),
                    "stop_loss": round(latest["close"] * 0.97, 2),
                    "score": score,
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
            except Exception:
                logger.exception("Error processing symbol %s", symbol)
                return None

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {executor.submit(evaluate_symbol, item): item for item in symbols}
            for future in as_completed(future_to_symbol):
                result = future.result()
                if result:
                    suggestions.append(result)

        suggestions.sort(key=self.tie_breaker)
        top_n = suggestions[:12]
        total_time = (time.perf_counter() - start_all)
        logger.info(
            "Completed get_suggestions: %d out of %d symbols, returned %d suggestions in %.2fs",
            len(suggestions), len(symbols), len(top_n), total_time
        )

        return top_n

    # Smarter sorting with tie-breakers
    def tie_breaker(self, x):
        return (
            -x.get("score", 0),                      # 1. Higher score
            -x.get("ADX_14", 0),                     # 2. Stronger trend
            abs(x.get("RSI", 50) - 50),              # 3. RSI closest to neutral
            -x.get("volume", 0),                     # 4. Optional: Higher volume
        )

    def execute_entry(self, suggestion: dict, quantity: int, timestamp):
        symbol = suggestion["symbol"]
        entry_price = suggestion["close"]
        score = suggestion["score"]
        breakdown = suggestion["breakdown"]
        indicators = {k: v for k, v in suggestion.items() if k in ["adx", "dmp", "dmn", "rsi", "macd", "macd_signal", "bb", "stochastic_k", "obv", "atr"]}

        self.data_provider.place_order(symbol=symbol, quantity=quantity, action="buy", timestamp = timestamp)
        diagnostics_tracker.record_entry(
            symbol=symbol,
            entry_time=timestamp,
            entry_price=entry_price,
            score=score,
            filters=breakdown,
            indicators=indicators
        )