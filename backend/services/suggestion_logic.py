import logging
from brokers.kite.kite_data_provider import KiteDataProvider
from config.filters_setup import load_filters
from services.entry_service import EntryService
from services.technical_analysis import prepare_indicators, calculate_score
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger("suggestion_logic")
logger.setLevel(logging.INFO)

class SuggestionLogic:
    def __init__(self, interval="day", index="all"):
        self.interval = interval
        self.index = index
        self.data_provider = KiteDataProvider(interval=interval, index=index)
        self.config = load_filters()
        self.weights = self.config.get("score_weights", {})
        self.min_price = self.config.get("min_price", 50)
        self.min_volume = self.config.get("min_volume", 100000)

    def score_single_stock(self, symbol: str):
        symbol = symbol.upper().strip()
        if not symbol.endswith(".NS"):
            symbol += ".NS"

        logger.info("Scoring single stock: %s", symbol)
        try:
            token = self.data_provider.get_token_for_symbol(symbol)
            if not token:
                raise ValueError(f"Instrument token not found for {symbol}")

            df = self.data_provider.fetch_ohlc({"symbol": symbol, "instrument_token": token})
            if df is None or df.empty:
                raise ValueError(f"No data available for {symbol}")

            df = prepare_indicators(df)
            latest = df.iloc[-1]

            if latest["close"] <= self.min_price or latest["volume"] < self.min_volume:
                logger.info("%s skipped due to low price or volume", symbol)
                return {
                    "symbol": symbol,
                    "score": 0,
                    "suggestion": "avoid",
                    "reason": "Low price or volume"
                }

            avg_rsi = df["RSI"].rolling(14).mean().iloc[-1]
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
            logger.error("Token expired while scoring %s", symbol)
            raise
        except Exception as e:
            logger.exception("Error scoring stock %s: %s", symbol, e)
            raise


def get_filtered_stock_suggestions(interval: str = "day", index: str = "nifty_50") -> list:
    logger.info("Fetching filtered stock suggestions for interval=%s, index=%s", interval, index)
    try:
        provider = KiteDataProvider(interval=interval, index=index)
        config = load_filters()
        service = EntryService(data_provider=provider, config=config)
        return service.get_suggestions()

    except InvalidTokenException:
        logger.error("Token expired during filtered suggestion fetch")
        raise
    except Exception as e:
        logger.exception("Unexpected error during get_filtered_stock_suggestions: %s", e)
        raise
