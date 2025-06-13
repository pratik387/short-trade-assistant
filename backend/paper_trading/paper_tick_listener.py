import threading
import logging
import json
from pathlib import Path
from kiteconnect import KiteTicker
from config.env_setup import env
from paper_trading.trade_manager import run_paper_trading_cycle, is_market_active
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("paper_tick_listener")
logger.setLevel(logging.INFO)

# Track current paper-trade subscriptions
tokens_subscribed = set()
# Thread reference for paper ticker
_ticker_thread = None
# KiteTicker instance for paper trades
ticker = KiteTicker(env.KITE_API_KEY, env.KITE_API_SECRET)

# Path to mock portfolio JSON located alongside this file
MOCK_PORTFOLIO_FILE = Path(__file__).resolve().parent / "mock_portfolio.json"

def get_paper_portfolio_tokens():
    """
    Retrieve instrument tokens for open paper-trading positions from mock_portfolio.json.
    """
    try:
        with open(MOCK_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            portfolio = json.load(f)
        return [entry.get("instrument_token") for entry in portfolio if entry.get("instrument_token")]
    except Exception as e:
        logger.exception(f"Paper: error reading mock_portfolio.json: {e}")
        return []


def update_subscriptions():
    """
    Subscribe/unsubscribe tokens based on current mock paper portfolio.
    """
    global tokens_subscribed
    current = set(get_paper_portfolio_tokens())
    new = list(current - tokens_subscribed)
    removed = list(tokens_subscribed - current)

    if new:
        ticker.subscribe(new)
        logger.info(f"Paper: subscribed to new tokens: {new}")
    if removed:
        ticker.unsubscribe(removed)
        logger.info(f"Paper: unsubscribed from tokens: {removed}")

    tokens_subscribed = current

@ticker.on_connect
def _on_connect(ws, response):
    """Subscribe when connected"""
    # If it's a holiday/weekend, disconnect immediately
    if not is_market_active():
        logger.info("Market not active at connect; closing ticker.")
        ws.close()
        return
    update_subscriptions()
    logger.info("Paper tick listener connected and subscriptions updated.")

@ticker.on_ticks
def _on_ticks(ws, ticks):
    """
    On each tick, run the paper-trading cycle for subscribed tokens.
    """
    for tick in ticks:
        token = tick.get("instrument_token")
        if token in tokens_subscribed:
            logger.debug(f"Paper: processing tick for token {token}")
            try:
                result = run_paper_trading_cycle([tick])
                logger.info(f"Paper-trade result for {token}: {result}")
            except Exception as e:
                logger.exception(f"Paper-trade error on tick {tick}: {e}")

@ticker.on_close
def _on_close(ws, code, reason):
    logger.info(f"Paper tick listener disconnected: {code} - {reason}")


def start_paper_tick_listener():
    """
    Start the KiteTicker in a background thread to process live market ticks.
    """
    global _ticker_thread
    if _ticker_thread and _ticker_thread.is_alive():
        logger.debug("Paper tick listener already running.")
        return
    _ticker_thread = threading.Thread(
        target=ticker.connect,
        kwargs={"threaded": True, "disable_ssl": False},
        daemon=True
    )
    _ticker_thread.start()
    logger.info("Paper tick listener started.")


def stop_paper_tick_listener():
    """
    Stop the paper-trade KiteTicker connection and thread.
    """
    try:
        ticker.stop()
    except Exception:
        logger.exception("Error stopping paper ticker.")
    global _ticker_thread
    if _ticker_thread:
        _ticker_thread.join(timeout=5)
        logger.info("Paper tick listener stopped.")
    else:
        logger.debug("Paper tick listener was not running.")

# Scheduler to start/stop listener at exact market open/close times
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
# Start at 9:15 AM IST, Mon-Fri
scheduler.add_job(
    start_paper_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=15)
)
# Stop at 3:30 PM IST, Mon-Fri
scheduler.add_job(
    stop_paper_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30)
)
# Start scheduler
scheduler.start()

# Immediately schedule start/stop; no polling required
if __name__ == "__main__":
    # On direct run, start listener if market active
    start_paper_tick_listener()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        stop_paper_tick_listener()
