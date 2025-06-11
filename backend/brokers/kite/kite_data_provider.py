import logging
from brokers.kite.fetch import fetch_kite_data
from brokers.data.indexes import get_index_symbols
from services.notification.sms_service import send_kite_login_sms
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger(__name__)

class KiteDataProvider:
    def __init__(self, interval: str = "day", index: str = "nifty_50"):
        self.interval = interval
        self.index = index

    def get_symbols(self):
        """Return all symbol-token mappings for the current index."""
        return get_index_symbols(self.index)

    def fetch_ohlc(self, item):
        """
        Fetch OHLC data for a stock with error handling for invalid session.
        """
        try:
            return fetch_kite_data(
                symbol=item["symbol"],
                instrument_token=item.get("instrument_token"),
                interval=self.interval
            )
        except InvalidTokenException:
            logger.critical("⛔ Invalid access token detected during fetch. Triggering login SMS.")
            try:
                send_kite_login_sms()
                logger.info("📩 Kite login SMS alert sent.")
            except Exception as sms_err:
                logger.error(f"❌ Failed to send SMS: {sms_err}")
            raise

    def get_token_for_symbol(self, symbol: str) -> int:
        """
        Lookup instrument_token for a given symbol from cached index.
        """
        for item in self.get_symbols():
            if item["symbol"] == symbol:
                return item.get("instrument_token")
        return None
