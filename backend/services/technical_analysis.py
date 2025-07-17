# @role: Prepares and computes indicators for entry signals
# @used_by: entry_service.py, exit_service.py, suggestion_logic.py
# @filter_type: logic
# @tags: technical, entry, indicators
# Updated filters with logging and symbol tagging for entry logic
import pandas as pd
from services.filters.candle_pattern_filter import bullish_candle_pattern_filter

from config.logging_config import get_loggers
logger, trade_logger = get_loggers()

def passes_hard_filters(latest: pd.Series, cfg: dict, symbol: str = "") -> bool:
    try:
        logger.debug(f"🔍 Evaluating hard filters for {symbol}")
        if not (cfg.get('rsi_min', 40) <= latest['RSI'] <= cfg.get('rsi_max', 70)): return False
        if latest['MACD'] <= latest['MACD_SIGNAL']: return False
        if latest['DMP_14'] <= latest['DMN_14']: return False
        logger.debug(f"✅ {symbol} passed all hard filters")
        return True
    except Exception as e:
        logger.exception(f"❌ Error in hard filter evaluation for {symbol}: {e}")
        return False

def calculate_score(latest: pd.Series, config: dict, avg_rsi: float, symbol: str = "", full_df=None) -> tuple[int, list]:
    try:
        score = 0
        breakdown = []
        weights = config.get("score_weights", {})

        # ADX check
        adx_val = latest.get("ADX_14")
        adx_min = config.get("adx_min", 30)
        adx_max = config.get("adx_max", 45)
        adx_weight = weights.get("adx")
        if adx_val is not None and adx_min <= adx_val <= adx_max:
            score += adx_weight
            breakdown.append(("ADX", adx_weight, f"ADX={adx_val:.2f} in [{adx_min}-{adx_max}]")
        )

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
        macd_signal = latest.get("MACD_SIGNAL")
        macd_weight = weights.get("macd")
        if macd_val is not None and macd_signal is not None and macd_val > macd_signal:
            macd_cap = config.get("macd_cap", 30)
            effective_weight = macd_weight if macd_val <= macd_cap else int(macd_weight * 0.5)
            score += effective_weight
            breakdown.append(("MACD", effective_weight, f"MACD={macd_val:.2f} > Signal={macd_signal:.2f} (Cap={macd_cap})"))

        # Bollinger Band check
        bb_val = latest.get("BB_%B")
        bb_lower = config.get("bb_lower")
        bb_upper = config.get("bb_upper")
        bb_width = ((latest.get("BB_UPPER") - latest.get("BB_LOWER")) / latest.get("BB_MIDDLE")) * 100 if latest.get("BB_MIDDLE") else 0
        bb_width_min = config.get("bb_width_min", 5)
        bb_weight = weights.get("bb")
        if bb_val is not None and bb_lower <= bb_val <= bb_upper and bb_width >= bb_width_min:
            score += bb_weight
            breakdown.append(("Bollinger Band", bb_weight, f"%B={bb_val:.2f} in [{bb_lower}-{bb_upper}], Width={bb_width:.2f}%"))

        # DMP vs DMN confirmation
        dmp = latest.get("DMP_14")
        dmn = latest.get("DMN_14")
        max_gap = config.get("max_dmp_dmn_gap", 15)
        dmp_weight = weights.get("dmp_dmn", 1)
        if dmp is not None and dmn is not None and dmp > dmn and (dmp - dmn) <= max_gap:
            score += dmp_weight
            breakdown.append(("DMP > DMN", dmp_weight, f"DMP={dmp:.2f} > DMN={dmn:.2f}, Gap={dmp - dmn:.2f}"))

        # Price above SMA 50
        close = latest.get("close")
        sma_50 = latest.get("SMA_50")
        price_sma_weight = weights.get("price_sma", 2)
        if close is not None and sma_50 is not None and close > sma_50:
            score += price_sma_weight
            breakdown.append(("Close > SMA50", price_sma_weight, f"Close={close:.2f} > SMA50={sma_50:.2f}"))

        # OBV check
        obv_val = latest.get("OBV")
        obv_weight = weights.get("obv")
        obv_min = config.get("obv_min")
        if obv_val is not None and obv_val > obv_min:
            score += obv_weight
            breakdown.append(("OBV", obv_weight, f"OBV={obv_val:.2f} > {obv_min}"))

        # ATR check
        atr_val = latest.get("ATR")
        atr_weight = weights.get("atr")
        atr_min = config.get("atr_min")
        if atr_val is not None and atr_val > atr_min:
            score += atr_weight
            breakdown.append(("ATR", atr_weight, f"ATR={atr_val:.2f} > {atr_min}"))

        # Stochastic check
        stoch_k = latest.get("STOCHASTIC_K")
        stoch_d = latest.get("STOCHASTIC_D")
        stoch_weight = weights.get("stochastic")
        stoch_threshold = config.get("stochastic_threshold")
        if stoch_k is not None and stoch_d is not None and stoch_k > stoch_d and stoch_k > stoch_threshold:
            score += stoch_weight
            breakdown.append(("Stochastic", stoch_weight, f"%K={stoch_k:.2f} > %D={stoch_d:.2f} & > {stoch_threshold}"))


        # Candle pattern check
        if full_df is not None and bullish_candle_pattern_filter(full_df):
            candle_weight = weights.get("candle_pattern")
            score += candle_weight
            breakdown.append(("Candle Pattern", candle_weight, "Pattern match"))

        # Fibonacci check (optional)
        fib_zone = latest.get("fibonacci_levels")
        fib_weight = weights.get("fibonacci_support")
        if fib_zone:
            score += fib_weight
            breakdown.append(("Fibonacci", fib_weight, f"In support zone"))

        # Late entry penalty
        lep_cfg = config.get("late_entry_penalty", {})
        lep_penalty = lep_cfg.get("penalty_score", 0)
        if rsi is not None and rsi > lep_cfg.get("rsi_above", 100):
            score += lep_penalty
            breakdown.append(("Late Entry Penalty", lep_penalty, f"RSI={rsi:.2f} > {lep_cfg.get('rsi_above')}"))
        if macd_val is not None and macd_val > lep_cfg.get("macd_above", 100):
            score += lep_penalty
            breakdown.append(("Late Entry Penalty", lep_penalty, f"MACD={macd_val:.2f} > {lep_cfg.get('macd_above')}"))

        return score, breakdown

    except Exception as e:
        logger.exception(f"❌ Error calculating score for {symbol}: {e}")
        return 0, []
