from tinydb import TinyDB, Query
from pathlib import Path
from datetime import datetime

PORTFOLIO_PATH = Path(__file__).resolve().parent / "mock_portfolio.json"
db = TinyDB(PORTFOLIO_PATH)
StockQuery = Query()


def add_mock_stock(symbol, price, quantity):
    if db.contains(StockQuery.symbol == symbol and StockQuery.status == "open"):
        return False

    db.insert({
        "symbol": symbol,
        "buy_price": price,
        "quantity": quantity,
        "status": "open",
        "buy_time": datetime.now().isoformat()
    })
    return True


def get_open_positions():
    return db.search(StockQuery.status == "open")


def mark_stock_sold(symbol):
    db.update({"status": "sold", "sell_time": datetime.now().isoformat()}, StockQuery.symbol == symbol)