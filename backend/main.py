# @role: FastAPI app entrypoint with route mounting and startup hooks
# @used_by: NA
# @filter_type: utility
# @tags: main, entrypoint, fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.suggestion_router import router as suggestion_router
from routes.portfolio_router import router as portfolio_router
from routes.notification_router import router as notification_router
from routes.kite_auth_router import kite_router 
from routes.cache_router import router as cache_router
from schedulers.scheduler import start, shutdown
from schedulers.tick_listener import start_tick_listener, stop_tick_listener
from config.logging_config import get_loggers

# Set up logging first
logger, trade_logger = get_loggers()

# App setup
app = FastAPI(title="Trading Assistant", version="1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(suggestion_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(kite_router, prefix="/api")
app.include_router(cache_router, prefix="/api")

# Scheduler hooks
@app.on_event("startup")
def start_background_scheduler():
    logger.info("🔁 Starting scheduler and tick listener...")
    start()
    start_tick_listener()

@app.on_event("shutdown")
def on_shutdown():
    logger.info("🛑 Shutting down scheduler and tick listener...")
    shutdown()
    stop_tick_listener()
