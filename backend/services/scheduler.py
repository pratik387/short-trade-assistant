from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from services.refresh_instrument_cache import refresh_index_cache
from services.holiday_calender_downloader import download_nse_holidays
import logging

logger = logging.getLogger("scheduler")
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

scheduler.start()
logger.info("✅ APScheduler started")
