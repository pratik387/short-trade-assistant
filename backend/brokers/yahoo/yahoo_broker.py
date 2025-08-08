from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from typing import List
from brokers.base_broker import BaseBroker
from brokers.data.indexes import get_index_symbols
from config.logging_config import get_loggers
logger, _ = get_loggers()

class YahooBroker(BaseBroker):
    def get_symbols(self, index):
        return get_index_symbols(index)

    def format_symbol(self, symbol):
        return symbol if symbol.endswith(".NS") else f"{symbol.upper()}.NS"

    def fetch_candles(self, symbol: str, interval: str, days: int = None,
                    from_date: datetime = None, to_date: datetime = None) -> pd.DataFrame:
        symbol = self.format_symbol(symbol)

        if not from_date or not to_date:
            if not days:
                raise ValueError("Either `days` or (`from_date` and `to_date`) must be provided")
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

        yf_interval = {
            "day": "1d",
            "5minute": "5m",
            "15minute": "15m"
        }.get(interval.lower(), "1d")

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=from_date, end=to_date + timedelta(days=1), interval=yf_interval)

        if df is None or df.empty:
            logger.warning(f"[YahooBroker] No data returned for {symbol}")
            return pd.DataFrame()
        
        df.index.name = "date"  # rename index
        df.reset_index(inplace=True)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        df = df[["date", "Open", "High", "Low", "Close", "Volume"]]

        # Rename and normalize
        df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume"
        }, inplace=True)

        # Final sanity check
        expected = {"date", "open", "high", "low", "close", "volume"}
        actual = set(df.columns)
        if not expected.issubset(actual):
            logger.warning(f"[YahooBroker] ❌ Unexpected columns in {symbol}: {actual}")
            return pd.DataFrame()

        return df

    def get_ltp(self, symbols: List[str]) -> dict:
        prices = {}
        for symbol in symbols:
            s = self.format_symbol(symbol)
            ticker = yf.Ticker(s)
            try:
                price = ticker.info.get("lastPrice") or ticker.history(period="1d")["Close"].iloc[-1]
                prices[symbol] = price
            except:
                prices[symbol] = None
        return prices

    def place_order(self, *args, **kwargs):
        raise NotImplementedError("YahooBroker does not support order placement")
