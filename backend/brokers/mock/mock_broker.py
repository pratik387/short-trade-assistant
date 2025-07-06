# @role: Mock broker for paper/backtesting purposes
# @used_by: base_broker.py, entry_service.py, exit_service.py, kite_broker.py, kite_client.py, suggestion_logic.py, trade_executor.py
# @filter_type: utility
# @tags: broker, mock, test
from datetime import datetime
from typing import Optional
import pandas as pd
from pathlib import Path
from brokers.base_broker import BaseBroker
from brokers.kite.kite_broker import KiteBroker
from brokers.data.indexes import get_index_symbols
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

class MockBroker(BaseBroker):
    def __init__(self, interval: str = "day", index: str = "nifty_50", use_cache: bool = True):
        self.use_cache = use_cache
        self.cache_dir = Path(__file__).resolve().parents[2] / "backtesting" / "ohlcv_cache"
        self.live_broker = KiteBroker()

    def get_ltp(self, symbol: str) -> float:
    
        if self.use_cache:
            file_path = self.cache_dir / f"{symbol}.feather"
            if file_path.exists():
                df = pd.read_feather(file_path)
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                if not df.empty:
                    return df.iloc[-1]["close"]
                else:
                    logger.warning(f"[MOCK][get_ltp] No data for {symbol}")
            else:
                logger.warning(f"[MOCK][get_ltp] File not found for {symbol}")

        return self.live_broker.get_ltp(symbol=symbol)


    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        days: int = None,
        from_date: datetime = None,
        to_date: datetime = None
    ):
        try:
            if self.use_cache:
                file_path = self.cache_dir / f"{symbol}.feather"
                if file_path.exists():
                    df = pd.read_feather(file_path)
                    df = df.set_index("date").sort_index()
                    df = df.sort_values("date")
                    if days and len(df) >= days:
                        return df.iloc[-days:].copy()
                    return df.copy()
            # fallback to API
            return self.live_broker.fetch_candles(symbol, interval, 180)
        except Exception as e:
            logger.error(str(e))
            return None

    def place_order(
        self,
        symbol: str,
        quantity: int,
        action: str,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        timestamp: Optional[datetime] = None
    ) -> dict:
        order_time = timestamp or datetime.now()
        logger.info(f"[MOCK] Placing order: {action.upper()} {quantity} {symbol} @ {price or 'market'}")
        return {
            "status": "success",
            "order_id": f"MOCK-{symbol[:3]}-{order_time.strftime('%H%M%S')}",
            "symbol": symbol,
            "qty": quantity,
            "action": action.upper(),
            "price": price or 100.0,
            "order_type": order_type.upper(),
            "product": "MIS",
            "variety": "regular",
            "timestamp": order_time.isoformat()
        }

    def get_symbols(self, index):
        """Return all symbol-token mappings for the current index."""
        return get_index_symbols(index)