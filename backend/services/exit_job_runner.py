# @role: Job runner that periodically triggers exit checks
# @used_by: tick_listener.py
# @filter_type: logic
# @tags: exit, job, scheduler
import logging
from pathlib import Path
from datetime import datetime

from services.exit_service import ExitService
from db.tinydb.client import get_table
from config.filters_setup import load_filters
from services.notification.email_alert import send_exit_email
from exceptions.exceptions import InvalidTokenException
from trading.trade_executor import TradeExecutor
from brokers.kite.kite_broker import KiteBroker

logger = logging.getLogger(__name__)

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

        # Data provider (broker used for fetching exit data)
        data_provider = KiteBroker()
        # Setup TradeExecutor with real broker
        broker = KiteBroker()
        trade_executor = TradeExecutor(broker=broker)

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
            trade_executor=trade_executor,
            notifier=notifier,
            blocked_logger=blocked_logger
        )

        service.check_exits()

        logger.info("✅ Exit check completed")

    except InvalidTokenException:
        logger.error("❌ Token expired during exit checks — exiting early")
        raise
    except Exception:
        logger.exception("❌ Unexpected error during exit checks")