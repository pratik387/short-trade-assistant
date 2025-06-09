from services.exit_service import ExitService
from brokers.kite.kite_exit_data_provider import KiteExitDataProvider
from db.tinydb.client import get_table
from config.settings import load_filter_config
from services.notification.email_alert import send_exit_email
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("exit_job")

def run_exit_checks():
    config = load_filter_config()
    portfolio_db = get_table("portfolio")
    data_provider = KiteExitDataProvider(interval="day", index="nifty_50")

    def notifier(symbol, price):
        try:
            send_exit_email(symbol, price)
            logger.info(f"Sent exit email for {symbol} at {price}")
        except Exception as e:
            logger.error(f"Failed to send exit email: {e}")

    def blocked_logger(message):
        path = Path("backend/blocked_exits.log")
        with open(path, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")

    service = ExitService(config, portfolio_db, data_provider, notifier, blocked_logger)
    service.check_exits()
