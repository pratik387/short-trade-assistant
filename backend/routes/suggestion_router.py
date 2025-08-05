# @role: Routes to serve filtered stock suggestions to frontend
# @used_by: exit_job_runner.py, exit_service.py
# @filter_type: system
# @tags: router, suggestion, api
from fastapi import APIRouter, HTTPException, Query
from exceptions.exceptions import InvalidTokenException
from pydantic import BaseModel
from datetime import datetime
from services.exit_service import ExitService
from brokers.kite.kite_broker import KiteBroker
from db.tinydb.client import get_table
from config.filters_setup import load_filters
from config.logging_config import get_loggers
from pytz import timezone as pytz_timezone
india_tz = pytz_timezone("Asia/Kolkata")

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
    strategy: str = Query("swing", description="Strategy: 'swing', 'intraday', etc."),
    index: str = Query("all", description="Index: 'nifty_50', 'nifty_100', etc.")
):
    logger.debug("get_suggestions called with interval=%s index=%s", strategy, index)
    try:
        suggestions = get_filtered_stock_suggestions( strategy=strategy, index=index)
        logger.info("Returning %d suggestions for %s/%s", len(suggestions), strategy, index)
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

@router.post("/check-exit")
def check_exit(request: ExitCheckRequest):
    try:
        config = load_filters()
        portfolio_db = get_table("portfolio")
        broker = KiteBroker()

        service = ExitService(
            config=config,
            portfolio_db=portfolio_db,
            data_provider=broker
        )

        stock = {
            "symbol": request.symbol,
            "entry_price": request.entry_price,
            "entry_date": request.entry_time,
            "score": getattr(request, "entry_score", 0)
        }

        result = service.evaluate_exit_decision(
            stock=stock,
            current_date=datetime.now(india_tz)
        )

        return {
            "symbol": result.get("symbol"),
            "recommendation": result.get("recommendation"),
            "exit_reason": result.get("exit_reason", ""),
            "pnl": round(float(result.get("pnl", 0)), 2),
            "pnl_percent": round(float(result.get("pnl_percent", 0)), 2),
            "reasons": result.get("reasons", []),
            "breakdown": result.get("breakdown", []),
            "days_held": result.get("days_held", 0),
            "current_price": result.get("current_price", 0),
            "entry_price": result.get("entry_price", 0)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
