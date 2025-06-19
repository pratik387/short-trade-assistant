from pydantic import BaseModel, Field
from typing import Optional

class PortfolioStock(BaseModel):
    symbol: str
    instrument_token: Optional[int] = None
    buy_price: float
    quantity: int
    status: str = Field(default="open")
    buy_time: str
    sell_time: Optional[str] = None

    # Optional trade metadata
    strategy: Optional[str] = None
    score: Optional[int] = None
    exit_reason: Optional[str] = None
    sell_price: Optional[float] = None
    pnl: Optional[float] = None

