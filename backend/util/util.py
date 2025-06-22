# @role: Helper utilities like date handling, price rounding etc.
# @used_by: exit_service.py, portfolio_router.py, technical_analysis_exit.py, tick_listener.py
# @filter_type: utility
# @tags: utility, helpers, tools
import pandas as pd
from pathlib import Path
import json
import logging
import time
import functools
from jobs.refresh_holidays import download_nse_holidays
from exceptions.exceptions import InvalidTokenException, DataUnavailableException
from brokers.kite.kite_client import set_access_token_from_file
logger = logging.getLogger("tick_listener")
logger.setLevel(logging.INFO)

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "assets" / "nse_holidays.json"
def is_market_active(date=None):
    """
    Check if the market is active for a given date/time.
    Loads holiday dates from the JSON file and applies weekend and session checks.
    Returns True if open, False if closed.
    """
    try:
        # Normalize date parameter or use today's date
        if date is None:
            check_date = pd.Timestamp.now(tz="Asia/Kolkata")
        else:
            check_date = pd.Timestamp(date)
            if check_date.tzinfo is None:
                check_date = check_date.tz_localize("Asia/Kolkata")
            else:
                check_date = check_date.tz_convert("Asia/Kolkata")

        # Weekend check (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            logger.info(f"⛔ {check_date.date()} is weekend; market closed.")
            return False

        # Load holiday entries
        try:
            with open(HOLIDAY_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except FileNotFoundError:
            logger.error(f"⚠️ Holidays file not found at {HOLIDAY_FILE!s}. Downloading fresh copy…")
            res = download_nse_holidays()
            if res.get("status") == "success":
                with open(HOLIDAY_FILE, "r", encoding="utf-8") as f:
                    items = json.load(f)
            else:
                logger.info("❌ Could not fetch holidays; assuming market is open.")
                return True

        # Parse holiday dates
        dates = []
        for item in items:
            # support both keys
            raw = item.get("tradingDate") or item.get("holidayDate")
            try:
                dt = pd.to_datetime(raw, format="%d-%b-%Y", errors="coerce").normalize()
                if not pd.isna(dt):
                    dates.append(dt)
            except Exception:
                continue

        if check_date in dates:
            logger.info(f"⛔ {check_date.date()} is a market holiday.")
            return False

        # Market session hours: 9:15am – 3:30pm IST
        open_time = check_date.replace(hour=9, minute=15)
        close_time = check_date.replace(hour=15, minute=30)
        is_open = open_time <= check_date <= close_time
        logger.info(f"Market status at {check_date.time()}: {'Open' if is_open else 'Closed'}")
        return is_open

    except Exception as e:
        logger.error(f"⚠️ Could not determine market status: {e}")
        return False
    
def retry(max_attempts=3, delay=2, exceptions=(Exception,), exclude=(InvalidTokenException,)):
    """
    Decorator to retry a function if it raises specified exceptions.

    Args:
        max_attempts (int): Number of retry attempts before giving up.
        delay (int): Delay between retries in seconds.
        exceptions (tuple): Tuple of exception classes to catch.

    Example:
        @retry(max_attempts=5, delay=1)
        def fetch_data(): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except InvalidTokenException as e:
                    logger.warning(f"[Retry {attempt}/{max_attempts}] Token error: {e}")
                    logger.info("🔄 Refreshing Kite token...")
                    set_access_token_from_file()  # reapply valid token
                    time.sleep(delay)
                except exceptions as e:
                    logger.warning(f"[Retry {attempt}/{max_attempts}] Exception: {e}")
                    if attempt == max_attempts:
                        logger.error(f"Exceeded max retries for {func.__name__}")
                        raise
                    if  'invalid token' in str(e).lower():
                        logger.error(f"Symbol not available in NSE {func.__name__}")
                        raise DataUnavailableException(f"Symbol not available in NSE : {e}")
                    time.sleep(delay)
        return wrapper
    return decorator