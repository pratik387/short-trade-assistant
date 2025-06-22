# @role: Broker interface implementation for Kite API
# @used_by: exit_job_runner.py, suggestion_logic.py, suggestion_router.py, tick_listener.py
# @filter_type: utility
# @tags: broker, kite, data_provider
import logging
from datetime import datetime, timedelta
import pandas as pd
from brokers.base_broker import BaseBroker
from brokers.kite.kite_client import kite
from brokers.data.indexes import get_index_symbols
from exceptions.exceptions import InvalidTokenException
logger = logging.getLogger("kite_broker")
from util.util import retry

class KiteBroker(BaseBroker):
    symbol_map = {
        s["symbol"]: s["instrument_token"]
        for s in get_index_symbols("all")
    }

    def get_symbols(self, index):
        """Return all symbol-token mappings for the current index."""
        return get_index_symbols(index)

    @retry()
    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        days: int = None,
        from_date: datetime = None,
        to_date: datetime = None
    ):
        try:
            instrument = self.symbol_map.get(symbol)
            if instrument is None:
                raise ValueError(f"Instrument token not found for {symbol}")

            if from_date is None or to_date is None:
                if days is None:
                    raise ValueError("Must provide either days or both from_date and to_date")
                to_date = datetime.now()
                from_date = to_date - timedelta(days=days)

            raw = kite.historical_data(
                instrument_token=instrument,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return self._format_ohlc_df(raw)

        except Exception as e:
            err_msg = str(e).lower()
            logger.warning(f"⚠️ Error fetching candles for {symbol}: {e}")

            if '429' in err_msg or 'too many requests' in err_msg or 'timeout' in err_msg:
                logger.info(f"🔁 Retry advised for {symbol} due to rate/timeout error")
                raise

            if any(t in err_msg for t in ['api_key', 'access_token']):
                logger.error(f"🚫 Token issue for {symbol}. Raising InvalidTokenException.")
                raise InvalidTokenException(f"Kite token invalid or expired: {e}")

            logger.error(f"❌ Non-retryable error for {symbol}: {e}")
            raise

    @retry()
    def place_order(self, symbol: str, quantity: int, action: str):
        try:
            exchange = "NSE"
            order_type = "MARKET"
            transaction_type = "BUY" if action.lower() == "buy" else "SELL"

            order_id = kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product="CNC"
            )
            logger.info(f"✅ Order placed: {symbol} {action} x {quantity} -> ID: {order_id}")
            return {
                "status": "success",
                "order_id": order_id,
                "symbol": symbol,
                "action": action,
                "quantity": quantity
            }
        except Exception as e:
            err_msg = str(e).lower()
            logger.exception(f"❌ Failed to place {action} order for {symbol}: {e}")

            if '429' in err_msg or 'too many requests' in err_msg or 'timeout' in err_msg:
                logger.info(f"🔁 Retry advised for {symbol} due to rate/timeout error")
                raise

            if any(t in err_msg for t in ['token', 'invalid', 'unauthorized']):
                logger.error(f"🚫 Token issue for {symbol}. Raising InvalidTokenException.")
                raise InvalidTokenException(f"Kite token invalid or expired: {e}")

            logger.error(f"❌ Non-retryable error for {symbol}: {e}")
            raise

    def _format_ohlc_df(self, raw):
        df = pd.DataFrame(raw)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df

    @retry()
    def get_ltp(self, symbol: str) -> float:
        try:
            quote = kite.ltp(f"NSE:{symbol}")
            return quote[f"NSE:{symbol}"]["last_price"]
        except Exception as e:
            logger.exception(f"Failed to fetch LTP for {symbol}: {e}")
            raise