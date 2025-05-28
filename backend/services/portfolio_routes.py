from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from tinydb import TinyDB, Query

router = APIRouter()

# File-backed TinyDB instance (persists across sessions)
db = TinyDB("portfolio.json")
StockQuery = Query()

class Stock(BaseModel):
    symbol: str
    close: float
    stop_loss: float

@router.get("/api/portfolio", response_model=List[Stock])
def get_portfolio():
    return db.all()

@router.post("/api/portfolio")
def add_to_portfolio(stock: Stock):
    if db.contains(StockQuery.symbol == stock.symbol):
        raise HTTPException(status_code=400, detail="Stock already tracked")
    db.insert(stock.dict())
    return {"message": f"{stock.symbol} added to portfolio"}

@router.delete("/api/portfolio/{symbol}")
def remove_from_portfolio(symbol: str):
    if not db.contains(StockQuery.symbol == symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
    db.remove(StockQuery.symbol == symbol)
    return {"message": f"{symbol} removed from portfolio"}

@router.post("/api/exit")
def trigger_exit_action(data: dict):
    symbol = data.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="Missing symbol")
    # Placeholder: In real use, trigger broker sell order
    return {"message": f"Exit triggered for {symbol}"}
