import logging
import time
from datetime import datetime, timedelta
import pandas as pd
from brokers.kite.kite_client import kite
from exceptions.exceptions import InvalidTokenException

logger = logging.getLogger(__name__)

def fetch_kite_data(symbol: str, instrument_token: int, interval: str = "day", max_retries: int = 3, backoff: float = 1.0) -> pd.DataFrame:
    """
    Retrieve historical OHLC data from Kite with retry logic.
    Raises InvalidTokenException if token is invalid.
    """
    if not instrument_token:
        logger.error(f"❌ Missing instrument token for {symbol}")
        return pd.DataFrame()

    to_date = datetime.today()
    if to_date.weekday() >= 5:
        to_date -= timedelta(days=(to_date.weekday() - 4))

    days = 100 if interval == "day" else 10
    from_date = to_date - timedelta(days=days)

    for attempt in range(1, max_retries + 1):
        try:
            data = kite.historical_data(instrument_token, from_date, to_date, interval)
            logger.info(f"✅ Retrieved data for {symbol} on attempt {attempt}")
            return pd.DataFrame(data)

        except Exception as e:
            err_msg = str(e).lower()
            logger.warning(f"⚠️ Attempt {attempt} for {symbol} failed: {e}")

            if '429' in err_msg or 'too many requests' in err_msg or 'timeout' in err_msg:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.info(f"🔁 Retrying {symbol} after {sleep_time}s due to rate/timeout error")
                time.sleep(sleep_time)
                continue

            if any(t in err_msg for t in ['token', 'invalid', 'unauthorized']):
                logger.error(f"🚫 Token issue for {symbol}. Raising InvalidTokenException.")
                raise InvalidTokenException(f"Kite token invalid or expired: {e}")

            logger.error(f"❌ Non-retryable error for {symbol}: {e}")
            break

    logger.error(f"❌ All {max_retries} attempts failed for {symbol}")
    return pd.DataFrame()
