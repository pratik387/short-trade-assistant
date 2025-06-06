from fastapi import APIRouter, Query
from backend.services.suggestion_logic import get_filtered_stock_suggestions

router = APIRouter()

@router.get("/api/short-term-suggestions")
def get_suggestions(
    interval: str = Query("day", description="Interval: 'day', '5minute', etc."),
    index: str = Query("all", description="Index: 'nifty_50', 'nifty_100', etc.")
):
    return get_filtered_stock_suggestions(interval=interval, index=index)
