# @role: Applies score-based filtering to suggest stocks
# @used_by: suggestion_router.py
# @filter_type: logic
# @tags: suggestion, scoring, logic
from config.filters_setup import load_filters
from services.entry_service import EntryService
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from exceptions.exceptions import InvalidTokenException
from brokers.kite.kite_broker import KiteBroker
from config.logging_config import get_loggers

# Set up logging first
logger, trade_logger = get_loggers()

def get_filtered_stock_suggestions(interval="day", index="nifty_50", strategy="intraday"):
    try:
        config = load_filters()
        data_provider = KiteBroker()
        entry_service = EntryService(data_provider, config, index, strategy)
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
        self.weights = self.config.get("entry_filters")
        self.min_price = self.config.get("min_price")
        self.min_volume = self.config.get("min_volume")

    def score_single_stock(self, symbol: str):
        try:
            df = self.data_provider.fetch_candles(symbol, self.interval, 180)
            if df is None or df.empty:
                return None

            enriched = enrich_with_indicators_and_score(df, self.config)
            latest = enriched.iloc[-1]

            if latest["close"] <= self.min_price or latest["volume"] < self.min_volume:
                logger.info("%s skipped due to low price or volume", symbol)
                return {
                    "symbol": symbol,
                    "score": 0,
                    "suggestion": "avoid",
                    "reason": "Low price or volume"
                }

            score = latest.get("ENTRY_SCORE")
            breakdown = latest.get("ENTRY_BREAKDOWN", [])
            suggestion = "buy" if score >= 15 else "avoid"

            logger.info(f"Scored {symbol}: {score:.2f} ({suggestion}) | Breakdown: {breakdown}")

            return {
                "symbol": symbol,
                "suggestion": suggestion,
                "close": round(latest["close"], 2),
                "volume": int(latest["volume"]),
                "score": float(score) if score is not None else 0.0,
                "breakdown": list(breakdown) if isinstance(breakdown, (list, tuple)) else [],
            }

        except InvalidTokenException:
            raise
        except Exception as e:
            logger.exception(f"Failed to score stock {symbol}: {e}")
            return None
