from brokers.kite.fetch import fetch_kite_data, InvalidAccessTokenError
from brokers.data.indexes import get_index_symbols
from services.notification.sms_service import send_kite_login_sms
import logging

logger = logging.getLogger(__name__)

class KiteDataProvider:
    def __init__(self, interval: str = "day", index: str = "nifty_50"):
        self.interval = interval
        self.index = index

    def get_symbols(self):
        return get_index_symbols(self.index)

    def fetch_ohlc(self, item):
        try:
            return fetch_kite_data(item["symbol"], item.get("instrument_token"), self.interval)
        except InvalidAccessTokenError as e:
            logger.critical("⛔ Invalid access token detected during exit checks. Triggering SMS login.")
            try:
                send_kite_login_sms()
                logger.info("📩 SMS sent for manual Kite login.")
            except Exception as sms_err:
                logger.error(f"❌ Failed to send SMS login reminder: {sms_err}")
    
    def get_token_for_symbol(self, symbol: str) -> int:
        """
        Returns the instrument_token for a given symbol.
        """
        all_symbols = self.get_symbols()
        for item in all_symbols:
            if item["symbol"] == symbol:
                return item.get("instrument_token")
        return None
