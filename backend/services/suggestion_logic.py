# @role: Applies score-based filtering to suggest stocks
# @used_by: suggestion_router.py
# @filter_type: logic
# @tags: suggestion, scoring, logic
from config.filters_setup import load_filters
from services.entry_service import EntryService
from services.indicator_enrichment_service import enrich_with_indicators_and_score
from exceptions.exceptions import InvalidTokenException
from brokers.kite.kite_broker import KiteBroker
from brokers.yahoo.yahoo_broker import YahooBroker
from config.logging_config import get_loggers

# NEW: use the single-path intraday screen+rank
from services.intraday_screener import screen_and_rank_intraday_candidates
from services.swing_screener import screen_and_rank_swing_candidates

from util.suggestion_storage import (
    store_suggestions_file,
    load_suggestions_file,
    suggestions_file_exists,
)

logger, trade_logger = get_loggers()


def get_filtered_stock_suggestions(strategy="swing", index="nifty_50", top_n_intraday: int = 7):
    """
    Entry point used by routes. For 'swing' keeps legacy behavior (no changes).
    For 'intraday', runs the new Phase-1 screen+rank to return a compact list
    of high-quality picks with plan objects.
    """
    try:
        config = load_filters()

        if suggestions_file_exists(index):
            suggestions = load_suggestions_file(index)
        else:
            data_provider_yahoo = YahooBroker()
            entry_service = EntryService(data_provider_yahoo, config, index)
            suggestions = entry_service.get_suggestions()
            store_suggestions_file(suggestions, index)

        if strategy == "intraday":
            data_provider = KiteBroker()
            # New: single-path ranked picks with plans (VWAP+vol gate, level-break confirm)
            return screen_and_rank_intraday_candidates(
                suggestions=suggestions,
                broker=data_provider,
                config=config,
                top_n=top_n_intraday,
            )
        else:
            data_provider = KiteBroker()
            # New: single-path ranked picks with plans (VWAP+vol gate, level-break confirm)
            return screen_and_rank_swing_candidates(
                suggestions=suggestions,
                broker=data_provider,
                config=config,
                top_n=top_n_intraday,
            )

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
