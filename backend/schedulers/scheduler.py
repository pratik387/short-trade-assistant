from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.jobs.refresh_instrument_cache import refresh_index_cache
from backend.jobs.refresh_holidays import download_nse_holidays
from services.exit_job_runner import run_exit_checks
from backend.services.notification.sms_service import send_kite_login_sms
import logging


logger = logging.getLogger("scheduler")
logging.basicConfig(level=logging.INFO)
scheduler = BackgroundScheduler()

scheduler.add_job(
    func=refresh_index_cache,
    trigger=CronTrigger(hour=3, minute=15, timezone="UTC"),
    id="daily_index_refresh",
    name="Refresh Index Cache if Market Open",
    replace_existing=True
)

scheduler.add_job(
    func=download_nse_holidays,
    trigger=CronTrigger(month=1, day=1, hour=3, minute=0, timezone="UTC"),
    id="annual_holiday_download",
    name="Download NSE Holiday Calendar",
    replace_existing=True
)

# Exit checks every 5 minutes (Asia/Kolkata time)
scheduler.add_job(
    func=run_exit_checks,
    trigger=CronTrigger(minute="*/5", timezone="Asia/Kolkata"),
    id="exit_checks",
    name="Periodic exit criteria evaluation",
    replace_existing=True
)

# Morning SMS reminder at 8:30 AM IST
scheduler.add_job(
    func=lambda: (logger.info("📲 Sending Kite login SMS..."), send_kite_login_sms()),
    trigger=CronTrigger(hour=10, minute=41, timezone="Asia/Kolkata"),
    id="kite_login_reminder",
    name="Send Kite Login SMS Link",
    replace_existing=True
)

def start():
    scheduler.start()
    logger.info("✅ APScheduler started")

def shutdown():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 APScheduler shut down")