from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.routes.kite_auth_router import kite_router
from backend.routes.portfolio_router import router as portfolio_router
from backend.routes.suggestion_router import router as suggestion_router
from backend.routes.mock_pnl_router import router as pnl_router
from backend.routes.cache_router import router as cache_router
from backend.routes.notification_router import router as notify_router
from backend.schedulers.scheduler import start as start_scheduler, shutdown as shutdown_scheduler
# TODO: remove after testing
from backend.paper_trading.scheduler import start as start_paper_scheduler, shutdown as stop_paper_scheduler


app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load .env
load_dotenv()

# Include all routers
app.include_router(kite_router)
app.include_router(portfolio_router)
app.include_router(suggestion_router)
app.include_router(pnl_router)
app.include_router(cache_router)
app.include_router(notify_router)

# ✅ Run scheduler during FastAPI startup
@app.on_event("startup")
async def start_background_scheduler():
    start_scheduler()
    # TODO: remove after testing
    start_paper_scheduler()

@app.on_event("shutdown")
async def on_shutdown():
    shutdown_scheduler()
    # TODO: remove after testing
    stop_paper_scheduler()