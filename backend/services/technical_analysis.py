# @role: Prepares and computes indicators for entry signals
# @used_by: entry_service.py, exit_service.py, suggestion_logic.py
# @filter_type: logic
# @tags: technical, entry, indicators
# Updated filters with breakout readiness, config modularization, and saturation guard
import pandas as pd
from services.filters.candle_pattern_filter import bullish_candle_pattern_filter

from config.logging_config import get_loggers
logger, trade_logger = get_loggers()

def passes_hard_filters(latest: pd.Series, cfg: dict, symbol: str = "") -> bool:
    try:
        logger.debug(f"🔍 Evaluating hard filters for {symbol}")
        rsi = latest.get("RSI")
        macd = latest.get("MACD")
        macd_signal = latest.get("MACD_SIGNAL")
        dmp = latest.get("DMP_14")
        dmn = latest.get("DMN_14")

        if not (cfg.get('rsi_min') <= rsi <= cfg.get('rsi_max')): return False
        if macd <= macd_signal: return False
        if dmp <= dmn: return False

        logger.debug(f"✅ {symbol} passed all hard filters")
        return True
    except Exception as e:
        logger.exception(f"❌ Error in hard filter evaluation for {symbol}: {e}")
        return False

def calculate_weighted_score(value: float, fcfg: dict, min_key="min", max_key="max") -> float:
    min_val = fcfg[min_key]
    max_val = fcfg[max_key]
    weight = fcfg["weight"]
    if min_val == max_val:
        return 0.0
    normalized = (value - min_val) / (max_val - min_val)
    normalized = max(0.0, min(normalized, 1.0))
    return round(normalized * weight, 2)

def calculate_score(latest: pd.Series, config: dict, symbol: str = "", full_df=None) -> tuple[int, list, dict]:
    try:
        score = 0
        breakdown = []
        filters = config.get("entry_filters", {})
        extras = {}

        def is_enabled(f): return filters.get(f).get("enabled")

        # ADX
        if is_enabled("adx"):
            fcfg = filters["adx"]
            adx = latest.get("ADX_14")
            if adx and fcfg["min"] <= adx <= fcfg["max"]:
                weighted = calculate_weighted_score(adx, fcfg)
                score += weighted
                breakdown.append({"filter": "adx", "weight": weighted, "details": {"adx": adx}})

        # RSI
        if is_enabled("rsi"):
            fcfg = filters["rsi"]
            rsi = latest.get("RSI")
            if rsi and fcfg["min"] <= rsi <= fcfg["max"]:
                weighted = calculate_weighted_score(rsi, fcfg)
                score += weighted
                breakdown.append({"filter": "rsi", "weight": weighted, "details": {"rsi": rsi}})

        # RSI > Avg RSI
        avg_rsi = latest.get("AVG_RSI")
        if is_enabled("rsi_above_avg") and rsi and avg_rsi and rsi > avg_rsi:
            val = filters["rsi_above_avg"]["weight"]
            score += val
            breakdown.append({"filter": "rsi_above_avg", "weight": val, "details": {"rsi": rsi, "avg_rsi": avg_rsi}})

        # MACD
        if is_enabled("macd"):
            fcfg = filters["macd"]
            macd = latest.get("MACD")
            signal = latest.get("MACD_SIGNAL")
            if macd and signal and macd > signal and macd >= fcfg.get("min", 0):
                cap = fcfg.get("cap", 30)
                gap = macd - signal
                normalized = min(gap / cap, 1.0)
                weighted = round(normalized * fcfg["weight"], 2)
                score += weighted
                breakdown.append({"filter": "macd", "weight": weighted, "details": {"macd": macd, "macd_signal": signal, "gap": gap, "cap": cap}})

        # Bollinger Band
        if is_enabled("bb"):
            fcfg = filters["bb"]
            bb_val = latest.get("BB_%B")
            mid = latest.get("BB_MIDDLE")
            width = ((latest.get("BB_UPPER") - latest.get("BB_LOWER")) / mid) * 100 if mid else 0
            if bb_val and fcfg["lower"] <= bb_val <= fcfg["upper"] and width >= fcfg["width_min"]:
                score += fcfg["weight"]
                breakdown.append({"filter": "bb", "weight": fcfg["weight"], "details": {"%B": bb_val, "width": width}})

        # DMP > DMN
        if is_enabled("dmp_dmn"):
            fcfg = filters["dmp_dmn"]
            dmp = latest.get("DMP_14")
            dmn = latest.get("DMN_14")
            if dmp and dmn and dmp > dmn and (dmp - dmn) <= fcfg["gap_max"]:
                score += fcfg["weight"]
                breakdown.append({"filter": "dmp_dmn", "weight": fcfg["weight"], "details": {"dmp": dmp, "dmn": dmn, "gap": dmp - dmn}})

        # Close > SMA50
        if is_enabled("price_sma"):
            fcfg = filters["price_sma"]
            close = latest.get("close")
            sma = latest.get("SMA_50")
            if close and sma and close > sma:
                if not fcfg.get("gap_max") or (close - sma) <= fcfg["gap_max"]:
                    score += fcfg["weight"]
                    breakdown.append({"filter": "price_sma", "weight": fcfg["weight"], "details": {"close": close, "sma50": sma}})

        # OBV
        if is_enabled("obv"):
            fcfg = filters["obv"]
            obv = latest.get("OBV")
            if obv and obv > fcfg["min"]:
                score += fcfg["weight"]
                breakdown.append({"filter": "obv", "weight": fcfg["weight"], "details": {"obv": obv}})

        # ATR
        if is_enabled("atr"):
            fcfg = filters["atr"]
            atr = latest.get("ATR")
            if atr and atr > fcfg["min"] and (not fcfg.get("max") or atr < fcfg["max"]):
                weighted = calculate_weighted_score(atr, fcfg)
                score += weighted
                breakdown.append({"filter": "atr", "weight": weighted, "details": {"atr": atr}})

        # Stochastic
        if is_enabled("stochastic"):
            fcfg = filters["stochastic"]
            k = latest.get("STOCHASTIC_K")
            d = latest.get("STOCHASTIC_D")
            if k and d and k > d and k > fcfg["threshold"]:
                score += fcfg["weight"]
                breakdown.append({"filter": "stochastic", "weight": fcfg["weight"], "details": {"%K": k, "%D": d}})
                if k > fcfg.get("penalty_above", 100):
                    score -= 1
                    breakdown.append({"filter": "stochastic_overbought", "weight": -1, "details": {"%K": k}})

        # Candle pattern
        if is_enabled("candle_pattern") and full_df is not None:
            fcfg = filters["candle_pattern"]
            if bullish_candle_pattern_filter(full_df):
                score += fcfg["weight"]
                breakdown.append({"filter": "candle_pattern", "weight": fcfg["weight"], "details": {"match": True}})

        # Fibonacci
        if is_enabled("fibonacci_support"):
            fcfg = filters["fibonacci_support"]
            if latest.get("fibonacci_levels"):
                score += fcfg["weight"]
                breakdown.append({"filter": "fibonacci_support", "weight": fcfg["weight"], "details": {"in_zone": True}})

        # Volume Surge
        if is_enabled("volume_surge"):
            fcfg = filters["volume_surge"]
            vol = latest.get("volume")
            vol_avg = latest.get("VOLUME_AVG")
            if vol and vol_avg:
                ratio = vol / vol_avg
                extras["volume_ratio"] = ratio
                surge_factor = fcfg.get("surge_factor")
                if ratio >= surge_factor:
                    normalized = min((ratio - surge_factor) / surge_factor, 1.0)
                    weighted = round(normalized * fcfg["weight"], 2)
                    score += weighted
                    breakdown.append({"filter": "volume_surge", "weight": weighted, "details": {"volume": vol, "avg_volume": vol_avg, "ratio": ratio}})

        # RSI Slope
        if is_enabled("rsi_slope") and full_df is not None:
            fcfg = filters["rsi_slope"]
            slope = full_df["RSI"].diff().rolling(3).mean().iloc[-1]
            min_slope = fcfg["min"]
            max_slope = fcfg["max"]
            if min_slope <= slope <= max_slope:
                weighted = calculate_weighted_score(slope, fcfg, min_key="min", max_key="max")
                score += weighted
                breakdown.append({"filter": "rsi_slope", "weight": weighted, "details": {"slope": slope}})

        # Breakout Ready
        if is_enabled("breakout_ready") and full_df is not None:
            fcfg = filters["breakout_ready"]
            bb_width = (full_df["BB_UPPER"] - full_df["BB_LOWER"]) / full_df["BB_MIDDLE"]
            bb_avg = bb_width.rolling(10).mean().iloc[-1]
            bb_now = bb_width.iloc[-1]
            rsi_slope = full_df["RSI"].diff().rolling(3).mean().iloc[-1]
            macd_hist_slope = full_df["MACD_HIST"].diff().rolling(3).mean().iloc[-1]

            bb_weight = 0
            rsi_weight = 0
            macd_weight = 0

            if bb_now < bb_avg * fcfg.get("bb_squeeze_factor"):
                bb_weight = round((1 - bb_now / (bb_avg * fcfg["bb_squeeze_factor"])) * fcfg["bb_weight"], 2)

            if fcfg["rsi_slope_min"] < rsi_slope < fcfg["rsi_slope_max"]:
                rsi_weight = calculate_weighted_score(rsi_slope, {
                    "min": fcfg["rsi_slope_min"],
                    "max": fcfg["rsi_slope_max"],
                    "weight": fcfg["rsi_weight"]
                })

            if macd_hist_slope > fcfg["macd_hist_slope_min"]:
                macd_weight = calculate_weighted_score(macd_hist_slope, {
                    "min": fcfg["macd_hist_slope_min"],
                    "max": fcfg.get("macd_hist_slope_max", macd_hist_slope + 1),
                    "weight": fcfg["macd_weight"]
                })

            total_weight = round(bb_weight + rsi_weight + macd_weight, 2)
            extras["breakout_ready"] = total_weight
            if total_weight > 0:
                score += total_weight
                breakdown.append({"filter": "breakout_ready", "weight": total_weight, "details": {"bb": bb_weight, "rsi": rsi_weight, "macd_hist": macd_weight}})

        # Late Entry Penalty
        lep_cfg = config.get("late_entry_penalty")
        rsi_threshold = lep_cfg.get("rsi_above")
        macd_threshold = lep_cfg.get("macd_above")
        penalty = lep_cfg.get("penalty_score")

        if rsi and rsi > rsi_threshold or (macd and macd > macd_threshold):
            score += penalty
            breakdown.append({"filter": "late_entry_penalty", "weight": penalty, "details": {"rsi": rsi, "macd": macd}})

        # Signal Saturation Block
        if score >= 20 and len(breakdown) >= 7:
            return 0, [{"filter": "signal_blocked", "weight": 0, "details": {"reason": "Signal saturation"}}]

        return score, breakdown, extras

    except Exception as e:
        logger.exception(f"❌ Error calculating score for {symbol}: {e}")
        return 0, []

