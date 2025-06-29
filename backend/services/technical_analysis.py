# @role: Prepares and computes indicators for entry signals
# @used_by: entry_service.py, exit_service.py, suggestion_logic.py
# @filter_type: logic
# @tags: technical, entry, indicators
# Updated filters with logging and symbol tagging for entry logic
import pandas as pd
from services.filters.adx_filter import calculate_adx
from services.filters.rsi_filter import calculate_rsi
from services.filters.bollinger_band_filter import calculate_bollinger_bands
from services.filters.macd_filter import calculate_macd
from services.filters.stochastic_filter import calculate_stochastic
from services.filters.obv_filter import calculate_obv
from services.filters.atr_filter import calculate_atr
from services.filters.fibonacci_filter import calculate_fibonacci_levels, is_fibonacci_support_zone

from config.logging_config import get_loggers
logger, trade_logger = get_loggers()

def prepare_indicators(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    try:
        logger.debug(f"🔍 Preparing indicators for {symbol}")
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

        fib_levels = []
        for idx in range(len(df)):
            window = df['close'].iloc[max(0, idx-19): idx+1]
            fib_levels.append(calculate_fibonacci_levels(window) if len(window) >= 2 else {})
        df['fibonacci_levels'] = fib_levels

        logger.debug(f"✅ Indicator preparation complete for {symbol}")
        return df
    except Exception as e:
        logger.exception(f"❌ Error preparing indicators for {symbol}: {e}")
        raise

def passes_hard_filters(latest: pd.Series, cfg: dict, symbol: str = "") -> bool:
    try:
        logger.debug(f"🔍 Evaluating hard filters for {symbol}")
        if latest['ADX_14'] < cfg.get('adx_threshold', 30): return False
        if not (cfg.get('rsi_min', 40) <= latest['RSI'] <= cfg.get('rsi_max', 70)): return False
        if latest['MACD'] <= latest['MACD_Signal']: return False
        if latest['DMP_14'] <= latest['DMN_14']: return False
        logger.debug(f"✅ {symbol} passed all hard filters")
        return True
    except Exception as e:
        logger.exception(f"❌ Error in hard filter evaluation for {symbol}: {e}")
        return False

def calculate_score(latest: pd.Series, config: dict, avg_rsi: float, candle_match: bool = False, symbol: str = "") -> tuple[int, list]:
    try:
        score = 0
        breakdown = []
        weights = config.get("score_weights", {})

        # ADX check
        adx_val = latest.get("ADX_14")
        adx_threshold = config.get("adx_threshold")
        adx_weight = weights.get("adx")
        if adx_val is not None and adx_val >= adx_threshold:
            score += adx_weight
            breakdown.append(("ADX", adx_weight, f"ADX={adx_val:.2f} ≥ {adx_threshold}"))

        # RSI check
        rsi = latest.get("RSI")
        rsi_min = config.get("rsi_min")
        rsi_max = config.get("rsi_max")
        rsi_weight = weights.get("rsi")
        if rsi is not None and rsi_min <= rsi <= rsi_max:
            score += rsi_weight
            breakdown.append(("RSI", rsi_weight, f"RSI={rsi:.2f} in [{rsi_min}-{rsi_max}]"))

        # RSI above average
        if rsi is not None and avg_rsi is not None and rsi > avg_rsi:
            val = weights.get("rsi_above_avg")
            score += val
            breakdown.append(("RSI > AvgRSI", val, f"RSI={rsi:.2f}, AvgRSI={avg_rsi:.2f}"))

        # MACD check
        macd_val = latest.get("MACD")
        macd_signal = latest.get("MACD_Signal")
        macd_weight = weights.get("macd")
        if macd_val is not None and macd_signal is not None and macd_val > macd_signal:
            score += macd_weight
            breakdown.append(("MACD", macd_weight, f"MACD={macd_val:.2f} > Signal={macd_signal:.2f}"))

        # Bollinger Band check
        bb_val = latest.get("BB_%B")
        bb_lower = config.get("bb_lower")
        bb_upper = config.get("bb_upper")
        bb_weight = weights.get("bb")
        if bb_val is not None and bb_lower <= bb_val <= bb_upper:
            score += bb_weight
            breakdown.append(("Bollinger Band", bb_weight, f"%B={bb_val:.2f} in [{bb_lower}-{bb_upper}]"))

        # DMP vs DMN confirmation
        dmp = latest.get("DMP_14")
        dmn = latest.get("DMN_14")
        dmp_weight = weights.get("dmp_dmn", 1)
        if dmp is not None and dmn is not None and dmp > dmn:
            score += dmp_weight
            breakdown.append(("DMP > DMN", dmp_weight, f"DMP={dmp:.2f} > DMN={dmn:.2f}"))

        # Price above SMA 50
        close = latest.get("close")
        sma_50 = latest.get("SMA_50")
        price_sma_weight = weights.get("price_sma", 2)
        if close is not None and sma_50 is not None and close > sma_50:
            score += price_sma_weight
            breakdown.append(("Close > SMA50", price_sma_weight, f"Close={close:.2f} > SMA50={sma_50:.2f}"))

        # OBV check
        obv_val = latest.get("obv")
        obv_weight = weights.get("obv")
        obv_min = config.get("obv_min")
        if obv_val is not None and obv_val > obv_min:
            score += obv_weight
            breakdown.append(("OBV", obv_weight, f"OBV={obv_val:.2f} > {obv_min}"))

        # ATR check
        atr_val = latest.get("atr")
        atr_weight = weights.get("atr")
        atr_min = config.get("atr_min")
        if atr_val is not None and atr_val > atr_min:
            score += atr_weight
            breakdown.append(("ATR", atr_weight, f"ATR={atr_val:.2f} > {atr_min}"))

        # Stochastic check
        stoch_k = latest.get("stochastic_k")
        stoch_d = latest.get("stochastic_d")
        stoch_weight = weights.get("stochastic")
        stoch_threshold = config.get("stochastic_threshold")
        if stoch_k is not None and stoch_d is not None and stoch_k > stoch_d and stoch_k > stoch_threshold:
            score += stoch_weight
            breakdown.append(("Stochastic", stoch_weight, f"%K={stoch_k:.2f} > %D={stoch_d:.2f} & > {stoch_threshold}"))

        # Candle pattern check
        if candle_match:
            candle_weight = weights.get("candle_pattern")
            score += candle_weight
            breakdown.append(("Candle Pattern", candle_weight, "Pattern match"))

        # Fibonacci check (optional)
        fib_zone = latest.get("fibonacci_levels")
        fib_weight = weights.get("fibonacci_support")
        if fib_zone:
            score += fib_weight
            breakdown.append(("Fibonacci", fib_weight, f"In support zone"))

        return score, breakdown

    except Exception as e:
        logger.exception(f"❌ Error calculating score for {symbol}: {e}")
        return 0, []
