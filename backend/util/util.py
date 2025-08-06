# @role: Helper utilities like date handling, price rounding etc.
# @used_by: exit_service.py, portfolio_router.py, technical_analysis_exit.py, tick_listener.py
# @filter_type: utility
# @tags: utility, helpers, tools
import pandas as pd
from pathlib import Path
import math
import json
import time
import functools
from datetime import datetime, timedelta
from jobs.refresh_holidays import download_nse_holidays
from exceptions.exceptions import InvalidTokenException, DataUnavailableException
from brokers.kite.kite_client import set_access_token_from_file
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

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

import math

def calculate_dynamic_exit_threshold(config, df, days_held):
    """
    Compute a dynamic score threshold for exit based on time decay and volatility.

    Args:
        config (dict): Full config object with 'exit_filters' and 'dynamic_threshold'
        df (pd.DataFrame): Enriched price data with 'ATR' column
        days_held (int): Days the stock has been held

    Returns:
        float: The computed dynamic threshold
    """
    dyn_config = config.get("dynamic_threshold", {})
    exit_filters = config.get("exit_filters", {})

    max_possible_score = 0
    for name, f in exit_filters.items():
        if not f.get("enabled", False):
            continue
        if name == "exit_time_decay_filter" and "weight_schedule" in f:
            scheduled_weights = [w.get("weight", 0) for w in f["weight_schedule"]]
            max_possible_score += max(scheduled_weights) if scheduled_weights else 0
        else:
            weight = f.get("weight", 0)
            if weight > 0:
                max_possible_score += weight

    base_ratio = dyn_config.get("base_weight_ratio", 0.25)
    min_threshold = dyn_config.get("min_threshold", 5)
    time_decay_rate = dyn_config.get("time_decay_rate", 0.3)
    time_weight_reduction = dyn_config.get("time_weight_reduction", 0.5)
    vol_scaling_factor = dyn_config.get("volatility_scaling_factor", 0.2)

    base_threshold = max(min_threshold, base_ratio * max_possible_score)
    time_decay = 1 - math.exp(-time_decay_rate * days_held)

    if "ATR" not in df.columns or df["ATR"].isna().all():
        return min_threshold

    current_atr = df["ATR"].iloc[-1]
    avg_atr = df["ATR"].rolling(window=14, min_periods=1).mean().fillna(0).iloc[-1]

    if avg_atr == 0:
        vol_adj = 1
    else:
        vol_adj = 1 + vol_scaling_factor * (current_atr / avg_atr)

    dynamic_threshold = base_threshold * (1 - time_weight_reduction * time_decay) * vol_adj
    return dynamic_threshold

def is_trading_day(date):
    """
    Returns True if the given date is a valid NSE trading day (not weekend, not holiday).
    Uses same holiday logic as is_market_active().
    """
    try:
        dt = pd.Timestamp(date).normalize()

        # Weekend
        if dt.weekday() >= 5:
            return False

        # Holidays (same logic)
        if not HOLIDAY_FILE.exists():
            download_nse_holidays()

        with open(HOLIDAY_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
            holidays = [
                pd.to_datetime(item.get("tradingDate") or item.get("holidayDate"), format="%d-%b-%Y", errors="coerce").normalize()
                for item in items
            ]
            holidays = [d for d in holidays if not pd.isna(d)]

        return dt not in holidays

    except Exception as e:
        logger.warning(f"⚠️ is_trading_day fallback triggered: {e}")
        return True  # fallback to assume trading day

def get_previous_trading_day(ref_date: datetime) -> datetime:
    prev_day = ref_date - timedelta(days=1)
    while not is_trading_day(prev_day):
        prev_day -= timedelta(days=1)
    return prev_day
