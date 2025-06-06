from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from tinydb import Query
from backend.db.tinydb.client import get_table

router = APIRouter()
StockQuery = Query()
portfolio = get_table("portfolio")


class Stock(BaseModel):
    symbol: str
    close: float
    quantity: Optional[int] = 100
    sold_targets: Optional[List[int]] = []
    highest_price: Optional[float] = None


@router.get("/api/portfolio", response_model=List[Stock])
def get_portfolio():
    return portfolio.all()


@router.post("/api/portfolio")
def add_to_portfolio(stock: Stock):
    if portfolio.contains(StockQuery.symbol == stock.symbol):
        raise HTTPException(status_code=400, detail="Stock already exists in portfolio")

    record = stock.dict()
    if record["highest_price"] is None:
        record["highest_price"] = record["close"]

    portfolio.insert(record)
    return {"message": "Stock added successfully"}


@router.put("/api/portfolio")
def update_stock(stock: Stock):
    if not portfolio.contains(StockQuery.symbol == stock.symbol):
        raise HTTPException(status_code=404, detail="Stock not found in portfolio")

    portfolio.update(stock.dict(), StockQuery.symbol == stock.symbol)
    return {"message": "Stock updated successfully"}


@router.delete("/api/portfolio/{symbol}")
def delete_stock(symbol: str):
    if not portfolio.contains(StockQuery.symbol == symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
    portfolio.remove(StockQuery.symbol == symbol)
    return {"message": f"Stock {symbol} deleted"}
