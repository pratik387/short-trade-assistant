# @role: Routes to serve filtered stock suggestions to frontend
# @used_by: exit_job_runner.py, exit_service.py
# @filter_type: system
# @tags: router, suggestion, api
from fastapi import APIRouter, HTTPException, Query
from exceptions.exceptions import InvalidTokenException
from pydantic import BaseModel
from datetime import datetime
from services.exit_service import ExitService
from trading.trade_executor import TradeExecutor
from brokers.kite.kite_broker import KiteBroker
from db.tinydb.client import get_table
from config.filters_setup import load_filters
from services.notification.email_alert import send_exit_email
from config.logging_config import get_loggers

from services.suggestion_logic import (
    get_filtered_stock_suggestions,
    SuggestionLogic
)

logger, trade_logger = get_loggers()

router = APIRouter()

@router.get(
    "/short-term-suggestions",
    summary="Get filtered short-term stock suggestions"
)
async def get_suggestions(
    interval: str = Query("day", description="Interval: 'day', '5minute', etc."),
    index: str = Query("all", description="Index: 'nifty_50', 'nifty_100', etc.")
):
    logger.debug("get_suggestions called with interval=%s index=%s", interval, index)
    try:
        suggestions = get_filtered_stock_suggestions(interval=interval, index=index)
        logger.info("Returning %d suggestions for %s/%s", len(suggestions), interval, index)
        return suggestions
    except InvalidTokenException:
        raise HTTPException(status_code=401, detail="Session expired—please log in again")
    except Exception:
        logger.exception("Unexpected error in get_filtered_stock_suggestions")
        raise HTTPException(
            status_code=500,
            detail="Internal error while fetching suggestions"
        )


@router.get(
    "/stock-score/{symbol}",
    summary="Compute score for a single stock"
)
async def score_single_stock(
    symbol: str,
    interval: str = Query("day", description="Interval for scoring")
):
    logger.debug("score_single_stock called for %s at interval=%s", symbol, interval)
    logic = SuggestionLogic(interval=interval)
    try:
        result = logic.score_single_stock(symbol)
        logger.info("Score for %s@%s: %s", symbol, interval, result["score"])
        return result
    except InvalidTokenException:
        raise HTTPException(status_code=401, detail="Session expired—please log in again")
    except Exception:
        logger.exception("Unexpected error scoring stock %s", symbol)
        raise HTTPException(
            status_code=500,
            detail="Internal error while scoring stock"
        )


class ExitCheckRequest(BaseModel):
    symbol: str
    entry_price: float
    entry_time: datetime

# Integrated into suggestion_router
@router.post("/check-exit")
def check_exit(request: ExitCheckRequest):
    try:
        config = load_filters()
        portfolio_db = get_table("portfolio")
        broker = KiteBroker()
        trade_executor = TradeExecutor(broker=broker)

        def notifier(symbol: str, price: float):
            try:
                send_exit_email(symbol, price)
            except Exception as e:
                print(f"❌ Failed to send email: {e}")

        def blocked_logger(message: str):
            print(f"[BLOCKED] {message}")

        service = ExitService(
            config=config,
            portfolio_db=portfolio_db,
            data_provider=broker,
            trade_executor=trade_executor,
            notifier=notifier
        )

        result = service.evaluate_exit_filters(
            symbol=request.symbol,
            entry_price=request.entry_price,
            entry_time=request.entry_time
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))