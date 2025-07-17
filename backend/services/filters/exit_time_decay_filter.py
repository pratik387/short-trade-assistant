# @role: Time-based filter to exit trades held beyond a duration threshold
# @used_by: technical_analysis_exit.py
# @filter_type: exit
# @tags: exit, decay, timing
from datetime import datetime
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()
def exit_time_decay_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("exit_time_decay_filter")
    if not filter_cfg.get("enabled", False):
        return []

    schedule = filter_cfg.get("weight_schedule")
    min_hold_days = filter_cfg.get("min_hold_days_for_exit", 3)
    weight = 0
    days_held = kwargs.get("days_held")
    for rule in sorted(schedule, key=lambda x: x["days"]):
        if days_held >= rule["days"]:
            weight = rule["weight"]
        else:
            break

    logger.info(f"[EXIT-TIME] {symbol} | Days Held={days_held}, Weight Applied={weight}")

    if days_held >= min_hold_days:
        return [{
            "filter": "exit_time_decay_filter",
            "weight": weight,
            "reason": f"Held for {days_held} days — applying weight {weight}",
            "triggered": True
        }]
    else:
        return [{
            "filter": "exit_time_decay_filter",
            "weight": 0,
            "reason": f"Holding period {days_held} < threshold {min_hold_days} days",
            "triggered": False
        }]
