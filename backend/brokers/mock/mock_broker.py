# @role: Mock broker for paper/backtesting purposes
# @used_by: base_broker.py, entry_service.py, exit_service.py, kite_broker.py, kite_client.py, suggestion_logic.py, trade_executor.py
# @filter_type: utility
# @tags: broker, mock, test
from datetime import datetime
from typing import List, Optional
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
            file_path = self.cache_dir / f"{symbol}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path, index_col="date", parse_dates=True)
                if not df.empty:
                    latest_close = df.iloc[-1]["close"]
                    return latest_close
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
                file_path = self.cache_dir / f"{symbol}.csv"
                if file_path.exists():
                    df = pd.read_csv(file_path, index_col="date", parse_dates=True)
                    return df
            # fallback to API
            return self.live_broker.fetch_candles(symbol, interval, 180)
        except Exception as e:
            logger.error(str(e))
    
    def place_order(
        self,
        symbol: str,
        quantity: int,
        action: str,
        price: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> dict:
        logger.info(f"[MOCK] Placing order: {action.upper()} {quantity} {symbol} @ {price or 'market'}")
        return {
            "status": "success",
            "order_id": f"MOCK-{symbol[:3]}-{datetime.now().strftime('%H%M%S')}",
            "symbol": symbol,
            "quantity": quantity,
            "action": action.upper(),
            "price": price or 100.0,
            "order_type": order_type.upper(),
            "product": "MIS",
            "variety": "regular",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_symbols(self, index):
        """Return all symbol-token mappings for the current index."""
        return get_index_symbols(index)