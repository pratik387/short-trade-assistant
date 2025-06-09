from fastapi import APIRouter, HTTPException, Query
from services.suggestion_logic import get_filtered_stock_suggestions
from services.suggestion_logic import SuggestionLogic


router = APIRouter()

@router.get("/api/short-term-suggestions")
def get_suggestions(
    interval: str = Query("day", description="Interval: 'day', '5minute', etc."),
    index: str = Query("all", description="Index: 'nifty_50', 'nifty_100', etc.")
):
    return get_filtered_stock_suggestions(interval=interval, index=index)

@router.get("/api/stock-score/{symbol}")
def score_single_stock(symbol: str, interval: str = Query("day")):
    logic = SuggestionLogic(interval=interval)
    try:
        return logic.score_single_stock(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
