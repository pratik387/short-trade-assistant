from fastapi import APIRouter, Request
from services.notification.email_alert import send_exit_email
import logging

router = APIRouter()
logger = logging.getLogger("notification")

@router.post("/api/send-exit-email")
async def trigger_exit_email(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    if symbol:
        logger.info(f"Triggering exit email for {symbol}")
        send_exit_email(symbol)
        return {"status": "email sent"}
    logger.warning("No symbol received for exit email")
    return {"status": "symbol missing"}
