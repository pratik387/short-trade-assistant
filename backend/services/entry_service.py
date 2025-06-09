import logging
from services.technical_analysis import prepare_indicators, passes_hard_filters, calculate_score

logger = logging.getLogger(__name__)

class EntryService:
    def __init__(self, data_provider, config):
        self.data_provider = data_provider
        self.config = config
        self.weights = config.get("score_weights", {})
        self.min_price = config.get("min_price", 50)
        self.min_volume = config.get("min_volume", 100000)

    def get_suggestions(self) -> list:
        suggestions = []
        rsi_vals = []

        symbols = self.data_provider.get_symbols()
        for item in symbols:
            df = self.data_provider.fetch_ohlc(item)
            if df is None or df.empty:
                continue

            df = prepare_indicators(df)
            latest = df.iloc[-1]
            if latest["close"] <= self.min_price or latest["volume"] < self.min_volume:
                continue

            if not passes_hard_filters(latest, self.config):
                continue

            rsi_vals.append(latest["RSI"])
            avg_rsi = sum(rsi_vals) / len(rsi_vals)
            score = calculate_score(latest, self.weights, avg_rsi, candle_match=False)

            suggestions.append({
                "symbol": item["symbol"],
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
                "close": round(float(latest["close"]), 2),
                "volume": int(latest["volume"]),
            })

        return sorted(suggestions, key=lambda x: x["score"], reverse=True)[:12]
