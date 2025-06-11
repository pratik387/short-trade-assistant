import logging
from pathlib import Path
from datetime import datetime

from services.exit_service import ExitService
from brokers.kite.kite_exit_data_provider import KiteExitDataProvider
from db.tinydb.client import get_table
from backend.config.filters_setup import load_filters
from services.notification.email_alert import send_exit_email
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger("exit_job")

def run_exit_checks():
    logger.info("🔍 Running exit checks...")
    try:
        config = load_filters()
        portfolio_db = get_table("portfolio")
        data_provider = KiteExitDataProvider(interval="day", index="nifty_50")

        def notifier(symbol, price):
            try:
                send_exit_email(symbol, price)
                logger.info(f"📧 Sent exit email for {symbol} at {price}")
            except Exception as e:
                logger.exception(f"❌ Failed to send exit email for {symbol}: {e}")

        def blocked_logger(message):
            try:
                path = Path("backend/blocked_exits.log")
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a") as f:
                    f.write(f"{datetime.now().isoformat()} - {message}\n")
            except Exception:
                logger.exception("Failed to log blocked exit message")

        service = ExitService(config, portfolio_db, data_provider, notifier, blocked_logger)
        service.check_exits()

        logger.info("✅ Exit check completed")

    except InvalidTokenException:
        logger.error("❌ Token expired during exit checks — exiting early")
        raise

    except Exception:
        logger.exception("❌ Unexpected error during exit checks")
