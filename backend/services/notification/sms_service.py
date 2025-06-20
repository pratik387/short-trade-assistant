# @role: Placeholder for SMS-based alerting service
# @used_by: tick_listener.py
# @filter_type: utility
# @tags: notification, sms, future
from datetime import datetime
from twilio.rest import Client
import os
import logging

logger = logging.getLogger("sms_service")

def send_kite_login_sms():
    kite_api_key = os.getenv("KITE_API_KEY")
    if not kite_api_key:
        raise ValueError("KITE_API_KEY not set in environment")

    kite_login_url = f"https://kite.zerodha.com/connect/login?api_key={kite_api_key}&v=3"

    account_sid = os.getenv("TWILIO_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_PHONE")
    your_number = os.getenv("YOUR_PHONE")

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Zerodha Kite Login: {kite_login_url}",
        from_=twilio_number,
        to=your_number
    )

    logger.info(f"✅ SMS sent to {your_number} with SID: {message.sid}")
    print("SMS sent with SID:", message.sid)