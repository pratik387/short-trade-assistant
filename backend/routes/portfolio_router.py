import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from tinydb import Query, TinyDB
from db.tinydb.client import get_table

# --- logger setup ---
logger = logging.getLogger("portfolio")
logger.setLevel(logging.INFO)

# --- TinyDB setup ---
StockQuery = Query()
portfolio: TinyDB = get_table("portfolio")

# --- Pydantic model ---
class Stock(BaseModel):
    symbol: str
    close: float
    quantity: int = 100
    sold_targets: List[int] = Field(default_factory=list)
    highest_price: Optional[float] = None

router = APIRouter()

@router.get("/api/portfolio", response_model=List[Stock])
def get_portfolio():
    logger.debug("Fetching full portfolio")
    try:
        records = portfolio.all()
        logger.info("Returned %d stocks from portfolio", len(records))
        return records
    except Exception:
        logger.exception("Failed to fetch portfolio")
        raise HTTPException(status_code=500, detail="Error reading portfolio")

@router.post("/api/portfolio")
def add_to_portfolio(stock: Stock):
    logger.debug("Adding stock %s to portfolio", stock.symbol)
    try:
        if portfolio.contains(StockQuery.symbol == stock.symbol):
            logger.warning("Stock %s already exists", stock.symbol)
            raise HTTPException(status_code=400, detail="Stock already exists in portfolio")

        data = stock.dict(exclude_none=True)
        # ensure highest_price is initialized
        data.setdefault("highest_price", data["close"])

        portfolio.insert(data)
        logger.info("Stock %s added successfully", stock.symbol)
        return {"message": "Stock added successfully"}

    except HTTPException:
        # re-raise known HTTP errors without logging again
        raise
    except Exception:
        logger.exception("Unexpected error adding %s", stock.symbol)
        raise HTTPException(status_code=500, detail="Error adding stock")

@router.put("/api/portfolio")
def update_stock(stock: Stock):
    logger.debug("Updating stock %s", stock.symbol)
    try:
        if not portfolio.contains(StockQuery.symbol == stock.symbol):
            logger.warning("Stock %s not found for update", stock.symbol)
            raise HTTPException(status_code=404, detail="Stock not found in portfolio")

        portfolio.update(stock.dict(exclude_none=True), StockQuery.symbol == stock.symbol)
        logger.info("Stock %s updated successfully", stock.symbol)
        return {"message": "Stock updated successfully"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error updating %s", stock.symbol)
        raise HTTPException(status_code=500, detail="Error updating stock")

@router.delete("/api/portfolio/{symbol}")
def delete_stock(symbol: str):
    logger.debug("Deleting stock %s", symbol)
    try:
        if not portfolio.contains(StockQuery.symbol == symbol):
            logger.warning("Stock %s not found for deletion", symbol)
            raise HTTPException(status_code=404, detail="Stock not found in portfolio")

        portfolio.remove(StockQuery.symbol == symbol)
        logger.info("Stock %s deleted successfully", symbol)
        return {"message": f"Stock {symbol} deleted"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error deleting %s", symbol)
        raise HTTPException(status_code=500, detail="Error deleting stock")
