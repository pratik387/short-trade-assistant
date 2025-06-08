from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from paper_trading.trade_manager import run_paper_trading_cycle, check_exit_conditions, is_market_active
import logging

logger = logging.getLogger("paper_scheduler")
scheduler = BackgroundScheduler()

# Helper to schedule only during market hours on weekdays
MARKET_HOURS = dict(day_of_week="mon-fri")

# Run paper trades at 10:00 and 14:00 IST
for hour in [10, 14]:
    scheduler.add_job(
        func=run_paper_trading_cycle,
        trigger=CronTrigger(hour=hour, minute=0, timezone="Asia/Kolkata", **MARKET_HOURS),
        id=f"paper_trade_{hour}",
        name=f"Run paper trading cycle at {hour}:00",
        replace_existing=True
    )

# Conditionally schedule exit checks if market is active
if is_market_active():
    scheduler.add_job(
        func=check_exit_conditions,
        trigger=CronTrigger(minute="*/5", timezone="Asia/Kolkata", **MARKET_HOURS),
        id="paper_trade_exit",
        name="Evaluate exit conditions",
        replace_existing=True
    )
else:
    logger.info("📅 Exit check job not scheduled — market inactive.")

scheduler.start()
logger.info("✅ Paper trade scheduler started")