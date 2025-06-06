from backend.brokers.kite.fetch import fetch_kite_data
from backend.data.indexes import get_index_symbols

class KiteExitDataProvider:
    def __init__(self, interval="day", index="nifty_50"):
        self.interval = interval
        self.index = index
        self.symbol_map = {s["symbol"]: s for s in get_index_symbols(index)}

    def fetch_exit_data(self, stock):
        symbol = stock.get("symbol")
        token = self.symbol_map.get(symbol, {}).get("instrument_token")
        if not symbol or not token:
            return None
        return fetch_kite_data(symbol, token, self.interval)
