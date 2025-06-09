from brokers.base_broker import BaseBroker
from brokers.kite.kite_client import get_kite

class KiteBroker(BaseBroker):
    def __init__(self):
        self.kite = get_kite()

    def place_order(self, symbol: str, quantity: int, action: str) -> dict:
        try:
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type=action.upper(),  # "BUY" or "SELL"
                quantity=quantity,
                order_type="MARKET",
                product="MIS",
                variety="regular"
            )
            return {"status": "success", "order_id": order_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}
