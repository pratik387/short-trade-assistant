from services.strategies.base_strategy import BaseStrategy
from config.logging_config import get_loggers
import pandas as pd
from typing import List

logger, _ = get_loggers()

class IntradayStrategy(BaseStrategy):
    def __init__(self, config):
        self.config = config
        self.mode = "intraday"

    def get_mode(self) -> str:
        return self.mode

    def apply_hard_filters(self, symbol: str, df: pd.DataFrame) -> bool:
        try:
            
            breakout_ready = df["breakout_ready"].iloc[-1] if "breakout_ready" in df.columns else 0
            vol_ratio = df["volume_ratio"].iloc[-1] if "volume_ratio" in df.columns else 0
            vol_ratio = df["volume_ratio"].iloc[-1] if "volume_ratio" in df.columns else 0
            rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else 0
            dmp = df["DMP_14"].iloc[-1] if "DMP_14" in df.columns else 0
            dmn = df["DMN_14"].iloc[-1] if "DMN_14" in df.columns else 0

            logger.debug(f"🔍 Evaluating hard filters for {symbol}")

            if breakout_ready < 0.25:
                logger.info(f"⚠️ Skipping {symbol}: insufficient breakout readiness ({breakout_ready})")
                return False

            if rsi > 63 and breakout_ready < 0.5:
                logger.info(f"⚠️ Skipping {symbol}: RSI ({rsi}) with insufficient breakout readiness ({breakout_ready})")
                return False

            if (dmp - dmn) < 5:
                logger.info(f"⚠️ Skipping {symbol}: Low DMP-DMN gap ({dmp - dmn})")
                return False

            if vol_ratio < 2.5:
                logger.info(f"⚠️ Skipping {symbol}: Insufficient volume ratio ({vol_ratio})")
                return False
            logger.debug(f"✅ {symbol} passed all hard filters")
            return True

        except Exception as e:
            logger.exception(f"❌ Error processing {symbol}")
            return False

