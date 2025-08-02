from services.strategies.base_strategy import BaseStrategy
from config.logging_config import get_loggers
import pandas as pd
from typing import List

logger, _ = get_loggers()

class IntradayStrategy(BaseStrategy):
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