import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

from jobs.refresh_instrument_cache import refresh_index_cache
from jobs.refresh_holidays import download_nse_holidays
from services.exit_job_runner import run_exit_checks
from services.notification.sms_service import send_kite_login_sms

# --- Logger setup ---
logger = logging.getLogger("scheduler")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- Scheduler init ---
scheduler = BackgroundScheduler()

def safe_job_runner(func, job_id: str):
    """Run `func` with structured logging and exception capture."""
    try:
        logger.info("▶ Job %s starting", job_id)
        func()
        logger.info("✔ Job %s completed successfully", job_id)
    except Exception:
        logger.exception("✖ Job %s failed with exception", job_id)

def job_listener(event: JobExecutionEvent):
    """Catch any errors or report durations after each job run."""
    if event.exception:
        logger.error("❌ Job %s raised an exception: %s", event.job_id, event.exception)
    else:
        # event.retval is typically None, you could instrument your funcs to return duration
        logger.info("🕒 Job %s executed without error", event.job_id)

# Attach listener for success & error events
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# --- Scheduled jobs ---

# 1) Daily index refresh at 03:15 UTC (if market open)
scheduler.add_job(
    func=lambda: safe_job_runner(refresh_index_cache, "daily_index_refresh"),
    trigger=CronTrigger(hour=3, minute=15, timezone="UTC"),
    id="daily_index_refresh",
    name="Refresh Index Cache if Market Open",
    replace_existing=True,
    misfire_grace_time=300,   # skip if >5 min late
    coalesce=True,            # collapse overlapping runs
)

# 2) Annual NSE holiday download: Jan 1 at 03:00 UTC
scheduler.add_job(
    func=lambda: safe_job_runner(download_nse_holidays, "annual_holiday_download"),
    trigger=CronTrigger(month=1, day=1, hour=3, minute=0, timezone="UTC"),
    id="annual_holiday_download",
    name="Download NSE Holiday Calendar",
    replace_existing=True,
    misfire_grace_time=3600,  # allow up to 1 hr delay
    coalesce=True,
)

# 3) Exit criteria evaluation every 5 min IST
scheduler.add_job(
    func=lambda: safe_job_runner(run_exit_checks, "exit_checks"),
    trigger=CronTrigger(minute="*/5", timezone="Asia/Kolkata"),
    id="exit_checks",
    name="Periodic exit criteria evaluation",
    replace_existing=True,
    misfire_grace_time=60,
    coalesce=False,           # run each missed occurrence
)

# 4) Morning SMS reminder at 08:30 AM IST
scheduler.add_job(
    func=lambda: safe_job_runner(send_kite_login_sms, "kite_login_reminder"),
    trigger=CronTrigger(hour=8, minute=30, timezone="Asia/Kolkata"),
    id="kite_login_reminder",
    name="Send Kite Login SMS Link",
    replace_existing=True,
    misfire_grace_time=300,
    coalesce=False,
)

def start():
    scheduler.start()
    logger.info("✅ APScheduler started")

def shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 APScheduler shut down")
