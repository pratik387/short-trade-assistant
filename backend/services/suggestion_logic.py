from backend.brokers.kite.kite_data_provider import KiteDataProvider
from backend.config.settings import load_filter_config
from backend.services.entry_service import EntryService
from backend.services.technical_analysis import prepare_indicators, calculate_score


class SuggestionLogic:
    def __init__(self, interval="day", index="all"):
        self.interval = interval
        self.index = index
        self.data_provider = KiteDataProvider(interval=interval, index=index)
        self.config = load_filter_config()
        self.weights = self.config.get("score_weights", {})
        self.min_price = self.config.get("min_price", 50)
        self.min_volume = self.config.get("min_volume", 100000)

    def score_single_stock(self, symbol: str):
        symbol = symbol.upper().strip()
        if not symbol.endswith(".NS"):
            symbol += ".NS"

        token = self.data_provider.get_token_for_symbol(symbol)
        if not token:
            raise ValueError(f"Instrument token not found for {symbol}")

        df = self.data_provider.fetch_ohlc({"symbol": symbol, "instrument_token": token})
        if df is None or df.empty:
            raise ValueError(f"No data available for {symbol}")

        df = prepare_indicators(df)
        latest = df.iloc[-1]

        if latest["close"] <= self.min_price or latest["volume"] < self.min_volume:
            return {
                "symbol": symbol,
                "score": 0,
                "suggestion": "avoid",
                "reason": "Low price or volume"
            }

        avg_rsi = df["RSI"].rolling(14).mean().iloc[-1]
        score = calculate_score(latest, self.weights, avg_rsi, candle_match=False)

        suggestion = "buy" if score >= 10 else "avoid"
        return {
            "symbol": symbol,
            "score": round(score, 2),
            "suggestion": suggestion,
            "close": round(latest["close"], 2),
            "volume": int(latest["volume"])
        }


def get_filtered_stock_suggestions(interval: str = "day", index: str = "nifty_50") -> list:
    """
    Utility method to get filtered stock suggestions programmatically.

    Args:
        interval (str): Timeframe like "day", "5minute", etc.
        index (str): Index filter like "nifty_50", "nifty_100", or "all".

    Returns:
        list: List of suggestion dicts with indicators and scores.
    """
    provider = KiteDataProvider(interval=interval, index=index)
    config = load_filter_config()
    service = EntryService(data_provider=provider, config=config)
    return service.get_suggestions()
