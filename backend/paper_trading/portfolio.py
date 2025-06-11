import logging
from datetime import datetime
from pathlib import Path
from tinydb import TinyDB, Query

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path(__file__).resolve().parent / "mock_portfolio.json"
db = TinyDB(PORTFOLIO_PATH)
StockQuery = Query()

def add_mock_stock(symbol, price, quantity):
    try:
        if db.search((StockQuery.symbol == symbol) & (StockQuery.status == "open")):
            logger.info(f"🚫 {symbol} already exists as an open position.")
            return False

        db.insert({
            "symbol": symbol,
            "buy_price": price,
            "quantity": quantity,
            "status": "open",
            "buy_time": datetime.now().isoformat()
        })
        logger.info(f"✅ Added mock stock: {symbol} at ₹{price} for qty {quantity}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add {symbol} to mock portfolio: {e}")
        return False

def get_open_positions():
    try:
        positions = db.search(StockQuery.status == "open")
        logger.info(f"📄 Retrieved {len(positions)} open positions.")
        return positions
    except Exception as e:
        logger.error(f"❌ Failed to fetch open positions: {e}")
        return []

def mark_stock_sold(symbol):
    try:
        updated = db.update(
            {"status": "sold", "sell_time": datetime.now().isoformat()},
            (StockQuery.symbol == symbol) & (StockQuery.status == "open")
        )
        if updated:
            logger.info(f"💸 Marked {symbol} as sold.")
        else:
            logger.warning(f"⚠️ No open entry found for {symbol} to mark as sold.")
    except Exception as e:
        logger.error(f"❌ Failed to mark {symbol} as sold: {e}")
