import threading
import logging
from kiteconnect import KiteTicker
from config.env_setup import env
from db.tinydb.client import get_table
from exit_job_runner import run_exit_checks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from util.util import is_market_active

logger = logging.getLogger("tick_listener")
logger.setLevel(logging.INFO)

# Track current subscriptions
tokens_subscribed = set()
# Thread reference for ticker
_ticker_thread = None
# KiteTicker instance
ticker = KiteTicker(env.KITE_API_KEY, env.KITE_API_SECRET)

def get_portfolio_tokens():
    """
    Retrieve all instrument tokens from the TinyDB portfolio (i.e., currently bought stocks).
    """
    try:
        entries = get_table.all()
        return [e["instrument_token"] for e in entries if e.get("instrument_token")]
    except Exception as e:
        logger.exception(f"Failed to load tokens from portfolio_db: {e}")
        return []


def update_subscriptions():
    """
    Subscribe to newly bought tokens and unsubscribe from exited tokens.
    """
    global tokens_subscribed
    current = set(get_portfolio_tokens())
    new = list(current - tokens_subscribed)
    removed = list(tokens_subscribed - current)

    if new:
        ticker.subscribe(new)
        logger.info(f"Subscribed to new tokens: {new}")
    if removed:
        ticker.unsubscribe(removed)
        logger.info(f"Unsubscribed from tokens: {removed}")

    tokens_subscribed = current

@ticker.on_connect
def _on_connect(ws, response):
    """Subscribe when connected"""
    # If connecting during non-market hours, disconnect immediately
    if not is_market_active():
        logger.info("Market not active at connect; closing ticker.")
        ws.close()
        return
    update_subscriptions()
    logger.info("Tick listener connected and subscriptions updated.")

@ticker.on_ticks
def _on_ticks(ws, ticks):
    """
    On each tick, run exit cycle for subscribed tokens.
    """
    for tick in ticks:
        token = tick.get("instrument_token")
        if token in tokens_subscribed:
            try:
                run_exit_checks([tick])
            except Exception as e:
                logger.exception(f"Error in exit cycle for tick {tick}: {e}")

@ticker.on_close
def _on_close(ws, code, reason):
    logger.info(f"Tick listener disconnected: {code} - {reason}")


def start_tick_listener():
    """
    Start the KiteTicker in a background thread to process live market ticks.
    """
    global _ticker_thread
    if _ticker_thread and _ticker_thread.is_alive():
        logger.debug("Tick listener already running.")
        return
    _ticker_thread = threading.Thread(
        target=ticker.connect,
        kwargs={"threaded": True, "disable_ssl": False},
        daemon=True
    )
    _ticker_thread.start()
    logger.info("Tick listener started.")


def stop_tick_listener():
    """
    Stop the KiteTicker connection and terminate the background thread.
    """
    try:
        ticker.stop()
    except Exception:
        logger.exception("Error stopping ticker.")
    global _ticker_thread
    if _ticker_thread:
        _ticker_thread.join(timeout=5)
        logger.info("Tick listener stopped.")
    else:
        logger.debug("Tick listener was not running.")

# Scheduler to start/stop listener at exact market open/close times
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
# Start at 9:15 AM IST, Mon-Fri
scheduler.add_job(
    start_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=15)
)
# Stop at 3:30 PM IST, Mon-Fri
scheduler.add_job(
    stop_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30)
)
# Start scheduler
scheduler.start()
