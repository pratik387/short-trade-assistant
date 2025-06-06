from backend.brokers.kite.fetch import fetch_kite_data
from backend.brokers.data.indexes import get_index_symbols

class KiteDataProvider:
    def __init__(self, interval: str = "day", index: str = "nifty_50"):
        self.interval = interval
        self.index = index

    def get_symbols(self):
        return get_index_symbols(self.index)

    def fetch_ohlc(self, item):
        return fetch_kite_data(item["symbol"], item.get("instrument_token"), self.interval)
