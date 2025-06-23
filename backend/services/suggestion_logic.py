# @role: Applies score-based filtering to suggest stocks
# @used_by: suggestion_router.py
# @filter_type: logic
# @tags: suggestion, scoring, logic
import logging
from config.filters_setup import load_filters
from services.entry_service import EntryService
from services.technical_analysis import prepare_indicators, calculate_score
from exceptions.exceptions import InvalidTokenException
from brokers.kite.kite_broker import KiteBroker

logger = logging.getLogger(__name__)

def get_filtered_stock_suggestions(interval="day", index="nifty_50"):
    try:
        config = load_filters()
        data_provider = KiteBroker()
        entry_service = EntryService(data_provider, config, index)
        return entry_service.get_suggestions()
    except InvalidTokenException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch filtered stock suggestions")
        return []


class SuggestionLogic:
    def __init__(self, interval="day"):
        self.interval = interval
        self.config = load_filters()
        self.data_provider = KiteBroker()
        self.weights = self.config.get("score_weights", {})
        self.min_price = self.config.get("min_price", 50)
        self.min_volume = self.config.get("min_volume", 100000)

    def score_single_stock(self, symbol: str):
        try:
            enriched_symbol = f"{symbol.upper()}.NS"
            df = self.data_provider.fetch_candles(enriched_symbol, self.interval, 180)
            if df is None or df.empty:
                return None

            enriched = prepare_indicators(df)
            latest = enriched.iloc[-1]

            if latest["close"] <= self.min_price or latest["volume"] < self.min_volume:
                logger.info("%s skipped due to low price or volume", symbol)
                return {
                    "symbol": symbol,
                    "score": 0,
                    "suggestion": "avoid",
                    "reason": "Low price or volume"
                }

            avg_rsi = enriched["RSI"].rolling(14).mean().iloc[-1]
            score = calculate_score(latest, self.weights, avg_rsi, candle_match=False)

            suggestion = "buy" if score >= 10 else "avoid"
            logger.info("Scored %s: %.2f (%s)", symbol, score, suggestion)

            return {
                "symbol": symbol,
                "score": round(score, 2),
                "suggestion": suggestion,
                "close": round(latest["close"], 2),
                "volume": int(latest["volume"])
            }
        except InvalidTokenException:
            raise
        except Exception as e:
            logger.exception(f"Failed to score stock {symbol}: {e}")
            return None