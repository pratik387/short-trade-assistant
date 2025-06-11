import logging
import time
from services.technical_analysis import prepare_indicators, passes_hard_filters, calculate_score
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger("entry_service")
logger.setLevel(logging.INFO)

class EntryService:
    def __init__(self, data_provider, config: dict):
        self.data_provider = data_provider
        self.config = config
        self.weights = config.get("score_weights", {})
        self.min_price = config.get("min_price", 50)
        self.min_volume = config.get("min_volume", 100_000)

    def get_suggestions(self) -> list:
        logger.info(
            "Starting get_suggestions (min_price=%s, min_volume=%s)",
            self.min_price, self.min_volume
        )
        start_all = time.perf_counter()

        suggestions = []
        rsi_vals = []

        symbols = self.data_provider.get_symbols() or []
        logger.debug("Fetched %d symbols to evaluate", len(symbols))

        for item in symbols:
            symbol = item.get("symbol")
            symbol_start = time.perf_counter()
            try:
                df = self.data_provider.fetch_ohlc(item)
                if df is None or df.empty:
                    logger.debug("No data for %s, skipping", symbol)
                    continue

                df = prepare_indicators(df)
                latest = df.iloc[-1]

                if latest["close"] <= self.min_price:
                    logger.debug("%s: close %s <= min_price %s, skipping",
                                 symbol, latest["close"], self.min_price)
                    continue
                if latest["volume"] < self.min_volume:
                    logger.debug("%s: volume %s < min_volume %s, skipping",
                                 symbol, latest["volume"], self.min_volume)
                    continue

                if not passes_hard_filters(latest, self.config):
                    logger.debug("%s did not pass hard filters, skipping", symbol)
                    continue

                rsi = float(latest["RSI"])
                rsi_vals.append(rsi)
                avg_rsi = sum(rsi_vals) / len(rsi_vals) if rsi_vals else rsi

                score = calculate_score(latest, self.weights, avg_rsi, candle_match=False)

                suggestions.append({
                    "symbol": symbol,
                    "adx": round(float(latest["ADX_14"]), 2),
                    "dmp": round(float(latest["DMP_14"]), 2),
                    "dmn": round(float(latest["DMN_14"]), 2),
                    "rsi": round(rsi, 2),
                    "macd": round(float(latest["MACD"]), 2),
                    "macd_signal": round(float(latest["MACD_Signal"]), 2),
                    "bb": round(float(latest.get("BB_%B", 0)), 2),
                    "stochastic_k": round(float(latest.get("stochastic_k", 0)), 2),
                    "obv": round(float(latest.get("obv", 0)), 2),
                    "atr": round(float(latest.get("atr", 0)), 2),
                    "stop_loss": round(latest["close"] * 0.97, 2),
                    "score": score,
                    "close": round(float(latest["close"]), 2),
                    "volume": int(latest["volume"]),
                })

                elapsed_ms = (time.perf_counter() - symbol_start) * 1000
                logger.debug("Processed %s in %.1fms, score=%.2f", symbol, elapsed_ms, score)

            except InvalidTokenException:
                logger.error("Token expired while processing %s — aborting suggestions", symbol)
                raise
            except Exception:
                logger.exception("Error processing symbol %s", symbol)
                continue

        suggestions.sort(key=lambda x: x["score"], reverse=True)
        top_n = suggestions[:12]
        total_time = (time.perf_counter() - start_all)
        logger.info(
            "Completed get_suggestions: %d out of %d symbols, returned %d suggestions in %.2fs",
            len(suggestions), len(symbols), len(top_n), total_time
        )

        return top_n
