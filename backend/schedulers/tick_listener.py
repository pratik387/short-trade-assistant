import threading
import logging
from kiteconnect import KiteTicker
from config.env_setup import env
from db.tinydb.client import get_table
from services.exit_job_runner import run_exit_checks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from util.util import is_market_active
from exceptions.exceptions import InvalidTokenException
from services.notification.sms_service import send_kite_login_sms
from brokers.kite.kite_client import kite, set_access_token_from_file, TOKEN_FILE

logger = logging.getLogger("tick_listener")
logger.setLevel(logging.INFO)

# Track current subscriptions
tokens_subscribed = set()
# Thread reference for ticker
_ticker_thread = None
# KiteTicker instance
# KiteTicker will be initialized in start_tick_listener()
ticker = None

# Helper to fetch tokens from the TinyDB portfolio
def get_portfolio_tokens():
    """
    Retrieve all instrument tokens from the TinyDB portfolio (i.e., currently bought stocks).
    """
    try:
        entries = get_table("portfolio").all()
        return [e.get("instrument_token") for e in entries if e.get("instrument_token")]
    except Exception as e:
        logger.exception(f"Failed to load tokens from portfolio_db: {e}")
        return []

# Subscription updater
def update_subscriptions():
    """
    Subscribe to newly bought tokens and unsubscribe from exited tokens.
    """
    global tokens_subscribed
    current = set(get_portfolio_tokens())
    new_tokens = current - tokens_subscribed
    removed_tokens = tokens_subscribed - current

    if new_tokens:
        ticker.subscribe(list(new_tokens))
        logger.info(f"Subscribed to new tokens: {list(new_tokens)}")
    if removed_tokens:
        ticker.unsubscribe(list(removed_tokens))
        logger.info(f"Unsubscribed from tokens: {list(removed_tokens)}")

    tokens_subscribed = current

# Callback handlers
def _on_connect(ws, response):
    """Triggered when the websocket connection is established."""
    if not is_market_active():
        logger.info("Market not active; closing ticker.")
        ws.close()
        return
    update_subscriptions()
    logger.info("Tick listener connected and subscriptions updated.")

def _on_ticks(ws, ticks):
    """
    Process incoming ticks for subscribed tokens.
    """
    for tick in ticks:
        token = tick.get("instrument_token")
        if token in tokens_subscribed:
            try:
                portfolio = get_table("portfolio").all()
                matched = next((s for s in portfolio if s.get("instrument_token") == token), None)
                if matched:
                    tick["symbol"] = matched["symbol"]
                    run_exit_checks([tick])
                else:
                    logger.warning(f"No matching portfolio entry found for token: {token}")
            except InvalidTokenException:
                message = "🛑 Token expired during tick processing. Please re-authenticate via Kite."
                logger.error(message)
                send_kite_login_sms(message)
                ticker.stop()
            except Exception as exc:
                logger.exception(f"Error processing tick {tick}: {exc}")

def _on_close(ws, code, reason):
    """Triggered when the websocket connection is closed."""
    logger.info(f"Tick listener disconnected: {code} - {reason}")
    if code == 1006:
        logger.warning("Unclean WebSocket disconnect (code 1006). Check access token validity or connectivity issues.")

# Register handlers explicitly
# Handlers will be set when ticker is initialized inside start_tick_listener()

# Control functions
def start_tick_listener():
    """
    Start the KiteTicker in a background thread to receive live ticks.
    Skip starting if the market is inactive.
    Validates the access token before connecting.
    """
    if not is_market_active():
        logger.info("⛔ Skipping tick listener startup — market is closed.")
        return
    try:
        set_access_token_from_file()
        kite.profile()  # Raises exception if token is invalid

        # Manually set access token for KiteTicker — must be passed as `access_token` arg in connect()
        with open(TOKEN_FILE) as f:
            access_token = f.read().strip()
    except Exception as e:
        message = f"🛑 Cannot start tick listener — invalid or expired token: {e}"
        logger.error(message)
        send_kite_login_sms()
        return

    global _ticker_thread, ticker
    ticker = KiteTicker(env.KITE_API_KEY, access_token=access_token)
    ticker.on_connect = _on_connect
    ticker.on_ticks = _on_ticks
    ticker.on_close = _on_close

    _ticker_thread = threading.Thread(
        target=ticker.connect,
        kwargs={"threaded": True},
        daemon=True
    )
    _ticker_thread.start()
    logger.info("Tick listener started.")

def stop_tick_listener():
    """
    Stop the KiteTicker and join the thread.
    """
    try:
        if ticker:
            ticker.stop()
    except Exception:
        logger.exception("Error stopping ticker.")
    global _ticker_thread
    if _ticker_thread:
        _ticker_thread.join(timeout=5)
        logger.info("Tick listener stopped.")
    else:
        logger.debug("Tick listener was not running.")

# Scheduler: run start/stop at market open/close
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(
    start_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=15)
)
scheduler.add_job(
    stop_tick_listener,
    trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30)
)
scheduler.start()
