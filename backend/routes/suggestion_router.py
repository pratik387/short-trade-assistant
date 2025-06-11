import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from exceptions.exceptions import InvalidTokenException

from services.suggestion_logic import (
    get_filtered_stock_suggestions,
    SuggestionLogic
)

logger = logging.getLogger("suggestions")
logger.setLevel(logging.INFO)

router = APIRouter()

@router.get(
    "/api/short-term-suggestions",
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
    "/api/stock-score/{symbol}",
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
    except Exception:
        logger.exception("Unexpected error scoring stock %s", symbol)
        raise HTTPException(
            status_code=500,
            detail="Internal error while scoring stock"
        )

