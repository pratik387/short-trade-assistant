import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import environment config
from config.env_setup import env

# Set up application logger
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.info(f"Starting Short Trade Assistant in '{env.ENV}' mode")

# Routers
from routes.kite_auth_router import kite_router
from routes.portfolio_router import router as portfolio_router
from routes.suggestion_router import router as suggestion_router
from routes.mock_pnl_router import router as pnl_router
from routes.cache_router import router as cache_router
from routes.notification_router import router as notify_router

# Schedulers
from schedulers.scheduler import start as start_scheduler, shutdown as shutdown_scheduler
# Paper trading scheduler (testing)
from paper_trading.scheduler import start as start_paper_scheduler, shutdown as stop_paper_scheduler

app = FastAPI(
    title="Short Trade Assistant",
    version="1.0.0"
)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(kite_router)
app.include_router(portfolio_router)
app.include_router(suggestion_router)
app.include_router(pnl_router)
app.include_router(cache_router)
app.include_router(notify_router)

# Startup event: run schedulers
@app.on_event("startup")
async def start_background_scheduler():
    logger.info("Starting schedulers...")
    start_scheduler()
    # TODO: remove after testing
    start_paper_scheduler()

# Shutdown event: stop schedulers
@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down schedulers...")
    shutdown_scheduler()
    # TODO: remove after testing
    stop_paper_scheduler()
