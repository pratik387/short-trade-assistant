import logging
from brokers.base_broker import BaseBroker
from brokers.kite.kite_client import get_kite
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger(__name__)

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
            logger.info(f"✅ Order placed for {symbol} [{action.upper()} x {quantity}], Order ID: {order_id}")
            return {"status": "success", "order_id": order_id}

        except Exception as e:
            err = str(e).lower()
            logger.error(f"❌ Failed to place order for {symbol}: {e}")

            if any(keyword in err for keyword in ['token', 'unauthorized', 'invalid']):
                raise InvalidTokenException(f"Token error while placing order: {e}")

            return {"status": "error", "message": str(e)}
