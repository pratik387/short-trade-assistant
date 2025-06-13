import logging
from pathlib import Path
from datetime import datetime

from services.exit_service import ExitService
from brokers.kite.kite_exit_data_provider import KiteExitDataProvider
from db.tinydb.client import get_table
from config.filters_setup import load_filters
from services.notification.email_alert import send_exit_email
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger("exit_job")
logger.setLevel(logging.INFO)


def run_exit_checks(ticks=None):
    """
    Run exit checks across the current portfolio.
    If `ticks` is provided (list of tick dicts), only those symbols are evaluated.
    Otherwise, the full portfolio is scanned.
    """
    logger.info("🔍 Running exit checks...")
    try:
        # Load filter configuration
        config = load_filters()

        # Get portfolio table
        portfolio_db = get_table("portfolio")

        # Data provider for exit-specific data
        data_provider = KiteExitDataProvider(interval="day", index="nifty_50")

        # Notifier: email alerts
        def notifier(symbol: str, price: float):
            try:
                send_exit_email(symbol, price)
                logger.info(f"📧 Sent exit email for {symbol} at {price}")
            except Exception as e:
                logger.exception(f"❌ Failed to send exit email for {symbol}: {e}")

        # Blocked logger: log failures to file
        def blocked_logger(message: str):
            try:
                path = Path(__file__).resolve().parent.parent / "logs" / "blocked_exits.log"
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} - {message}\n")
            except Exception:
                logger.exception("Failed to log blocked exit message")

        # Instantiate service
        service = ExitService(
            config=config,
            portfolio_db=portfolio_db,
            data_provider=data_provider,
            notifier=notifier,
            blocked_logger=blocked_logger
        )

        # Execute exit checks for ticks or full portfolio
        if ticks:
            # Extract symbol names from ticks
            symbols = {tick.get("symbol") for tick in ticks if tick.get("symbol")}
            if symbols:
                logger.debug(f"Checking exits for symbols from ticks: {symbols}")
                service.check_exits(symbols=list(symbols))
        else:
            service.check_exits()

        logger.info("✅ Exit check completed")

    except InvalidTokenException:
        logger.error("❌ Token expired during exit checks — exiting early")
        raise
    except Exception:
        logger.exception("❌ Unexpected error during exit checks")
