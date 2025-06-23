# @role: Sends alerts and notifications (email, future SMS/WhatsApp)
# @used_by: project_map.py
# @filter_type: system
# @tags: router, notification, email
from fastapi import APIRouter, Request, HTTPException
from services.notification.email_alert import send_exit_email
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/send-exit-email")
async def trigger_exit_email(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    price = data.get("price")

    if not symbol:
        logger.warning("Missing symbol in email trigger request")
        raise HTTPException(status_code=400, detail="Missing 'symbol' in request")

    logger.info(f"Triggering exit email for {symbol} at price {price}")
    try:
        send_exit_email(symbol, price)
        return {"status": "email sent"}
    except Exception as e:
        logger.exception("Error while sending email for %s", symbol)
        raise HTTPException(status_code=500, detail="Email send failure")