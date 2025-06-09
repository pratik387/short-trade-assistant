import logging
import time
from datetime import datetime, timedelta
import pandas as pd
from routes.kite_auth_router import kite

logger = logging.getLogger(__name__)

class InvalidAccessTokenError(Exception):
    pass

def fetch_kite_data(symbol: str, instrument_token: int, interval: str = "day", max_retries: int = 3, backoff: float = 1.0) -> pd.DataFrame:
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

            if any(t in err for t in ['token', 'invalid', 'unauthorized']):
                logger.error(f"🛑 Invalid or expired token for {symbol}: {e}")
                raise InvalidAccessTokenError(f"Access token expired or invalid for {symbol}") from e

            logger.warning(f"⚠️ Attempt {attempt} for {symbol} failed: {e}")

            if '429' in err or 'too many requests' in err or 'timeout' in err:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.info(f"⏳ Backing off {sleep_time}s before retrying {symbol}")
                time.sleep(sleep_time)
            else:
                break

    logger.error(f"❌ All {max_retries} attempts failed for {symbol}")
    return pd.DataFrame()
