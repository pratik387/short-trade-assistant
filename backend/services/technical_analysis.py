# @role: Prepares and computes indicators for entry signals
# @used_by: entry_service.py, exit_service.py, suggestion_logic.py
# @filter_type: logic
# @tags: technical, entry, indicators
# Updated filters with logging and symbol tagging for entry logic
import logging
import pandas as pd
from services.filters.adx_filter import calculate_adx
from services.filters.rsi_filter import calculate_rsi
from services.filters.bollinger_band_filter import calculate_bollinger_bands
from services.filters.macd_filter import calculate_macd
from services.filters.stochastic_filter import calculate_stochastic
from services.filters.obv_filter import calculate_obv
from services.filters.atr_filter import calculate_atr
from services.filters.fibonacci_filter import calculate_fibonacci_levels, is_fibonacci_support_zone

logger = logging.getLogger(__name__)

def prepare_indicators(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    try:
        logger.info(f"🔍 Preparing indicators for {symbol}")
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()

        df = calculate_bollinger_bands(df, symbol=symbol)
        df = calculate_macd(df, symbol=symbol)
        df = df.join(calculate_adx(df[['high', 'low', 'close']], symbol=symbol))

        r = calculate_rsi(df[['close']], symbol=symbol)
        df['RSI'] = r['RSI'] if isinstance(r, pd.DataFrame) else r

        df = df.join(calculate_stochastic(df, symbol=symbol))
        df = df.join(calculate_obv(df, symbol=symbol))
        df = df.join(calculate_atr(df, symbol=symbol))

        # Compute fibonacci levels per row over a rolling window of closes
        fib_levels = []
        for idx in range(len(df)):
            window = df['close'].iloc[max(0, idx-19): idx+1]
            if len(window) >= 2:
                fib_levels.append(calculate_fibonacci_levels(window))
            else:
                fib_levels.append({})
        df['fibonacci_levels'] = fib_levels

        logger.info(f"✅ Indicator preparation complete for {symbol}")
        return df

    except Exception as e:
        logger.exception(f"❌ Error preparing indicators for {symbol}: {e}")
        raise

def passes_hard_filters(latest: pd.Series, cfg: dict, symbol: str = "") -> bool:
    try:
        logger.info(f"🔍 Evaluating hard filters for {symbol}")
        if latest['ADX_14'] < cfg.get('adx_threshold', 30): return False
        if not (cfg.get('rsi_min', 40) <= latest['RSI'] <= cfg.get('rsi_max', 70)): return False
        if latest['MACD'] <= latest['MACD_Signal']: return False
        if latest['DMP_14'] <= latest['DMN_14']: return False
        if not is_fibonacci_support_zone(latest['close'], latest['fibonacci_levels'], symbol=symbol): return False
        logger.info(f"✅ {symbol} passed all hard filters")
        return True
    except Exception as e:
        logger.exception(f"❌ Error in hard filter evaluation for {symbol}: {e}")
        return False

def calculate_score(latest: pd.Series, weights: dict, avg_rsi: float, candle_match: bool, symbol: str = "") -> int:
    try:
        score = 0
        if latest['ADX_14'] >= weights.get('adx', 3): score += weights['adx']
        if latest['MACD'] > latest['MACD_Signal']: score += weights.get('macd', 3)
        if weights.get('bb_lower', 0.2) < latest['BB_%B'] < weights.get('bb_upper', 0.8): score += weights.get('bb', 1)
        if latest['DMP_14'] > latest['DMN_14']: score += weights.get('dmp_dmn', 1)
        if latest['close'] > latest['SMA_50']: score += weights.get('price_sma', 2)
        if latest['RSI'] > avg_rsi: score += weights.get('rsi_above_avg', 1)
        if latest.get('stochastic_k', 0) > 50: score += weights.get('stochastic', 2)
        if latest.get('obv', 0) > 0: score += weights.get('obv', 2)
        if latest.get('atr', 0) > 0: score += weights.get('atr', 1)
        if candle_match: score += weights.get('candle_pattern', 2)
        logger.info(f"[SCORE] {symbol} | Final Score: {score}")
        return score
    except Exception as e:
        logger.exception(f"❌ Error calculating score for {symbol}: {e}")
        return 0
