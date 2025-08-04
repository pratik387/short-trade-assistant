from services.strategies.base_strategy import BaseStrategy
from config.logging_config import get_loggers
import pandas as pd
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger, _ = get_loggers()

class SwingStrategy(BaseStrategy):
    def __init__(self, config):
        self.config = config
        self.mode = "swing"

    def get_mode(self) -> str:
        return self.mode

    def apply_hard_filters(self, symbol: str, df: pd.DataFrame) -> bool:
        try:
            logger.debug(f"🔍 Evaluating hard filters for {symbol}")
            rsi = df.get("RSI")
            macd = df.get("MACD")
            macd_signal = df.get("MACD_SIGNAL")
            dmp = df.get("DMP_14")
            dmn = df.get("DMN_14")

            if not (self.config.get('rsi_min') <= rsi <= self.config.get('rsi_max')): return False
            if macd <= macd_signal: return False
            if dmp <= dmn: return False

            logger.debug(f"✅ {symbol} passed all hard filters")
            return True
        except Exception as e:
            logger.exception(f"❌ Error in hard filter evaluation for {symbol}: {e}")
            return False
        
    def preload_and_filter_symbols(self, symbols, data_provider, config, as_of_date):
        candle_cache = {}
        filtered_symbols = []
        lock = threading.Lock()

        def load_symbol(item):
            symbol = item.get("symbol")
            try:
                from_date = as_of_date - timedelta(days=config.get("lookback_days", 180))
                df = data_provider.fetch_candles(
                    symbol=symbol,
                    interval=config.get("interval", "day"),
                    from_date=from_date,
                    to_date=as_of_date
                )
                
                if df is None or df.empty:
                    return

                with lock:
                    candle_cache[symbol] = df
                    filtered_symbols.append(item)
            except Exception:
                logger.exception("Error preloading or filtering %s", symbol)

        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(load_symbol, item): item for item in symbols}
            for future in as_completed(futures):
                try:
                    future.result()  # will raise if load_symbol errored
                except Exception as e:
                    logger.error(f"Exception in preload thread: {e}")


        return filtered_symbols, candle_cache