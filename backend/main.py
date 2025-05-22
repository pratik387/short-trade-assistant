from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from email_alert import send_exit_email
import logging
from dotenv import load_dotenv
from services.kite_service import get_filtered_stock_suggestions
from services.kite_auth import kite_router

app = FastAPI()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("main")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Use router from kite_auth (which includes /kite-login-url and /kite-callback)
app.include_router(kite_router)

# Load other env variables if needed
load_dotenv()

@app.post("/api/send-exit-email")
async def trigger_exit_email(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    if symbol:
        logger.info(f"Triggering exit email for {symbol}")
        send_exit_email(symbol)
        return {"status": "email sent"}
    logger.warning("No symbol received for exit email")
    return {"status": "symbol missing"}

@app.get("/api/short-term-suggestions")
def get_suggestions():
    return get_filtered_stock_suggestions("day")