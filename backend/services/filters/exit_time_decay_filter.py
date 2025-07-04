# @role: Time-based filter to exit trades held beyond a duration threshold
# @used_by: technical_analysis_exit.py
# @filter_type: exit
# @tags: exit, decay, timing
from datetime import datetime
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()
india_tz = pytz_timezone("Asia/Kolkata")

def time_decay_filter(entry_price, entry_time, df, current_date, duration_threshold: int=5, pnl_threshold: float=0.01, symbol: str = "") -> tuple[bool, str]:
    current_price = df["close"].iloc[-1]
    pnl = (current_price - entry_price) / entry_price
    days_held = (current_date - entry_time).days
    logger.info(f"[EXIT-TIME] {symbol} | Days Held={days_held}, PnL={pnl:.2%}, Threshold={pnl_threshold:.2%}")
    if days_held >= duration_threshold and pnl < pnl_threshold:
        return True, f"Low return ({pnl:.2%}) after {days_held} days"
    return False, f"P&L={pnl:.2%} after {days_held} days (within acceptable range)"