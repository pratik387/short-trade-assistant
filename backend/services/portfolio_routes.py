from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from tinydb import TinyDB, Query

router = APIRouter()

# File-backed TinyDB instance
db = TinyDB("backend/portfolio.json")
StockQuery = Query()


class Stock(BaseModel):
    symbol: str
    close: float
    quantity: Optional[int] = 100
    sold_targets: Optional[List[int]] = []
    highest_price: Optional[float] = None


@router.get("/api/portfolio", response_model=List[Stock])
def get_portfolio():
    return db.all()


@router.post("/api/portfolio")
def add_to_portfolio(stock: Stock):
    if db.contains(StockQuery.symbol == stock.symbol):
        raise HTTPException(status_code=400, detail="Stock already exists in portfolio")

    record = stock.dict()
    if record["highest_price"] is None:
        record["highest_price"] = record["close"]
    db.insert(record)
    return {"message": "Stock added successfully"}


@router.put("/api/portfolio")
def update_stock(stock: Stock):
    if not db.contains(StockQuery.symbol == stock.symbol):
        raise HTTPException(status_code=404, detail="Stock not found in portfolio")

    db.update(stock.dict(), StockQuery.symbol == stock.symbol)
    return {"message": "Stock updated successfully"}


@router.delete("/api/portfolio/{symbol}")
def delete_stock(symbol: str):
    if not db.contains(StockQuery.symbol == symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
    db.remove(StockQuery.symbol == symbol)
    return {"message": f"Stock {symbol} deleted"}
