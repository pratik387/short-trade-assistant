import logging
from datetime import datetime
from typing import List, Optional

from brokers.base_broker import BaseBroker
from brokers.kite.kite_broker import KiteBroker

logger = logging.getLogger("mock_broker")

class MockBroker(BaseBroker):
    def __init__(self, interval: str = "day", index: str = "nifty_50"):
        self.live_broker = KiteBroker(interval=interval, index=index)

    def get_ltp(self, symbols: List[str]) -> dict:
        return self.live_broker.get_ltp(symbols)

    def fetch_candles(self, symbol: str, interval: str, token: Optional[int]) -> list:
        return self.live_broker.fetch_candles(symbol, interval, token)

    def get_instrument_token(self, symbol: str) -> Optional[int]:
        return self.live_broker.get_instrument_token(symbol)

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
