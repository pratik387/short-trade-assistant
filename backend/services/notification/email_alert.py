# @role: Sends email alerts for exit notifications
# @used_by: exit_job_runner.py, suggestion_router.py
# @filter_type: utility
# @tags: notification, email, alert
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

load_dotenv()

def send_exit_email(symbol: str):
    user = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_PASS")
    to = os.getenv("ALERT_TO")

    msg = EmailMessage()
    msg["Subject"] = f"Exit Alert for {symbol}"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(f"🚨 Exit signal triggered for {symbol}. Check your dashboard for more details.")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)

    return True