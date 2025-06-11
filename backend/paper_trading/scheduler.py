from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from paper_trading.trade_manager import run_paper_trading_cycle, check_exit_conditions, is_market_active
import logging

logger = logging.getLogger("paper_scheduler")
scheduler = BackgroundScheduler()

MARKET_HOURS = dict(day_of_week="mon-fri")
exit_job_id = "paper_trade_exit"

# Paper trading buy cycle at 10:00 and 14:00 IST
for hour in [10, 14]:
    scheduler.add_job(
        func=run_paper_trading_cycle,
        trigger=CronTrigger(hour=hour, minute=0, timezone="Asia/Kolkata", **MARKET_HOURS),
        id=f"paper_trade_{hour}",
        name=f"Run paper trading cycle at {hour}:00",
        replace_existing=True
    )

# def manage_exit_job():
#     """Check market status every 10 min and manage the exit job."""
#     if is_market_active():
#         if not scheduler.get_job(exit_job_id):
#             logger.info("📈 Market active. Scheduling exit job.")
#             scheduler.add_job(
#                 func=check_exit_conditions,
#                 trigger=CronTrigger(minute="*/5", timezone="Asia/Kolkata", **MARKET_HOURS),
#                 id=exit_job_id,
#                 name="Evaluate exit conditions",
#                 replace_existing=True
#             )
#     else:
#         if scheduler.get_job(exit_job_id):
#             logger.info("📉 Market inactive. Removing exit job.")
#             scheduler.remove_job(exit_job_id)

# Check every 10 minutes to dynamically manage exit job
# scheduler.add_job(
#     func=manage_exit_job,
#     trigger=CronTrigger(minute="*/5", timezone="Asia/Kolkata"),
#     id="manage_exit_scheduler",
#     name="Manage exit job based on market status",
#     replace_existing=True
# )

def start():
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ Paper trading scheduler started")

def shutdown():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Paper trading scheduler shut down")
