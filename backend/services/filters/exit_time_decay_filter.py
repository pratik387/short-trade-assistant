from datetime import datetime, timezone

def time_decay_filter(entry_price, entry_time, df) -> tuple[bool, str]:
    current_price = df["close"].iloc[-1]
    pnl = (current_price - entry_price) / entry_price
    days_held = (datetime.now(timezone.utc) - entry_time).days
    if days_held >= 5 and pnl < 0.01:
        return True, f"Low return ({pnl:.2%}) after {days_held} days"
    return False, ""