import logging
import time
from datetime import datetime, timedelta
import pandas as pd
from backend.authentication.kite_auth import kite

logger = logging.getLogger(__name__)


def fetch_kite_data(symbol: str, instrument_token: int, interval: str = "day", max_retries: int = 3, backoff: float = 1.0) -> pd.DataFrame:
    """
    Retrieve historical data with retry on transient failures (rate limits, network).
    """
    if not instrument_token:
        logger.error(f"Missing instrument token for {symbol}")
        return pd.DataFrame()

    to_date = datetime.today()
    if to_date.weekday() >= 5:
        to_date -= timedelta(days=to_date.weekday() - 4)
    days = 100 if interval == "day" else 10
    from_date = to_date - timedelta(days=days)

    attempt = 0
    while attempt < max_retries:
        try:
            data = kite.historical_data(instrument_token, from_date, to_date, interval)
            return pd.DataFrame(data)
        except Exception as e:
            err = str(e).lower()
            attempt += 1
            logger.warning(f"Attempt {attempt} for {symbol} failed: {e}")
            # Rate limit or transient network errors
            if '429' in err or 'too many requests' in err or 'timeout' in err:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.info(f"Backing off {sleep_time}s before retrying {symbol}")
                time.sleep(sleep_time)
                continue
            # On auth errors, bail immediately
            if any(t in err for t in ['token', 'invalid', 'unauthorized']):
                logger.error(f"Auth error for {symbol}: {e}")
                break
            # Other errors, no retry
            break
    logger.error(f"All {max_retries} attempts failed for {symbol}")
    return pd.DataFrame()