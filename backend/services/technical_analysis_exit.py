# @role: Prepares and computes exit indicators and filter evaluations
# @used_by: exit_service.py
# @filter_type: exit
# @tags: exit, logic, filters

import pandas as pd
from datetime import datetime
from config.logging_config import get_loggers
from services.filters.exit_rsi_filter import rsi_exit_filter
from services.filters.exit_bb_filter import bb_exit_filter
from services.filters.exit_obv_filter import obv_exit_filter
from services.filters.exit_atr_squeeze_filter import atr_squeeze_filter
from services.filters.exit_fibonacci_filter import fibonacci_exit_filter
from services.filters.exit_fibonacchi_support_filter import fibonacci_support_exit_filter
from services.filters.exit_macd_filter import macd_exit_filter
from services.filters.exit_time_decay_filter import exit_time_decay_filter
from services.filters.exit_override_filter import override_filter
from services.filters.exit_supply_absorption_filter import supply_absorption_filter
from services.filters.exit_pattern_breakdown_filter import pattern_breakdown_filter
from services.filters.exit_volatility_spike_filter import volatility_spike_exit


logger, trade_logger = get_loggers()

def evaluate_exit(
    df: pd.DataFrame,
    entry_price: float,
    entry_time: datetime,
    current_date: datetime,
    config,
    fallback_on_error=True,
    symbol: str = ""
):
    reasons = []

    try:
        # Phase 1: Immediate exit if override triggered
        override_results = override_filter(df, config=config, symbol=symbol, entry_price=entry_price, entry_time=entry_time, current_date=current_date)
        if isinstance(override_results, list):
            reasons.extend(override_results)
            if any(r.get("triggered") for r in override_results):
                return {
                    "raw_reasons": reasons,
                    "triggered": [r for r in reasons if r.get("triggered")],
                    "score": sum(r["weight"] for r in reasons if r.get("triggered")),
                    "exit_reason": "override",
                    "recommendation": "EXIT"
                }

        # Phase 2: Run all other filters
        for filter_func in [
            rsi_exit_filter,
            bb_exit_filter,
            obv_exit_filter,
            atr_squeeze_filter,
            fibonacci_exit_filter,
            fibonacci_support_exit_filter,
            macd_exit_filter,
            exit_time_decay_filter,
            supply_absorption_filter,
            pattern_breakdown_filter,
            volatility_spike_exit,
        ]:
            results = filter_func(df, config=config.get("exit_filters"), symbol=symbol, entry_price=entry_price, entry_time=entry_time, current_date=current_date, days_held=(current_date - entry_time).days)
            if isinstance(results, list):
                reasons.extend(results)

        # Score
        triggered = [r for r in reasons if r.get("triggered")]
        score = sum(r["weight"] for r in triggered)

        return {
            "raw_reasons": reasons,
            "triggered": triggered,
            "score": score
        }


    except Exception as e:
        logger.warning(f"Exit evaluation failed: {e}")
        if fallback_on_error:
            return {
                "raw_reasons": [],
                "triggered": [],
                "score": 0,
            }
        else:
            raise
