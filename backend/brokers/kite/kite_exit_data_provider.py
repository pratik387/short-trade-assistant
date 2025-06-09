from backend.brokers.kite.fetch import fetch_kite_data, InvalidAccessTokenError
from backend.brokers.data.indexes import get_index_symbols
from backend.services.notification.sms_service import send_kite_login_sms
import logging

logger = logging.getLogger(__name__)

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
        try:
            return fetch_kite_data(symbol, token, self.interval)
        except InvalidAccessTokenError as e:
            logger.critical("⛔ Invalid access token detected during exit checks. Triggering SMS login.")
            try:
                send_kite_login_sms()
                logger.info("📩 SMS sent for manual Kite login.")
            except Exception as sms_err:
                logger.error(f"❌ Failed to send SMS login reminder: {sms_err}")
