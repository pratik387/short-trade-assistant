from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.services.email_alert import send_exit_email
import logging
from dotenv import load_dotenv
from services.kite_service import get_filtered_stock_suggestions
from services.refresh_instrument_cache import refresh_index_cache
from backend.authentication.kite_auth import kite_router
from services.portfolio_routes import router as portfolio_router
from fastapi import Query

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

app.include_router(kite_router)
app.include_router(portfolio_router)

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

# Accepted values for `index`:
# "all" - All NSE stocks
# "nifty_50" - NIFTY 50 index
# "nifty_100" - NIFTY 100 index
# "nifty_200" - NIFTY 200 index
# "nifty_500" - NIFTY 500 index

@app.get("/api/short-term-suggestions")
def get_suggestions(interval: str = Query("day"), index: str = Query("all")):
    return get_filtered_stock_suggestions(interval=interval, index=index)

@app.post("/api/refresh-index-cache")
def refresh_index_cache_route():
    return refresh_index_cache()
