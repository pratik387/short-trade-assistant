# @role: Executes buy/sell actions through broker interface
# @used_by: exit_job_runner.py, suggestion_router.py
# @filter_type: utility
# @tags: trading, execution, broker
import logging
from datetime import datetime
from brokers.base_broker import BaseBroker
from util.portfolio_schema import PortfolioStock
from db.tinydb.client import get_table
from exceptions.exceptions import OrderPlacementException

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, broker: BaseBroker):
        self.broker = broker
        self.portfolio_db = get_table("portfolio")

    def execute_trade(self, symbol: str, instrument_token: int, quantity: int, action: str, price: float, order_type: str = "MARKET"):
        logger.info("[TRADE] Executing %s %d of %s at %s mode", action.upper(), quantity, symbol, order_type.upper())

        if not self.broker:
            logger.error("Trade execution failed: broker not configured")
            raise OrderPlacementException("No broker configured for trades")

        result = self.broker.place_order(
            symbol=symbol,
            quantity=quantity,
            action=action,
            price=price,
            order_type=order_type
        )
        logger.info("Trade result for %s: %s", symbol, result)

        if result.get("status") in ["success", "mocked"]:
            stock_entry = PortfolioStock(
                symbol=symbol,
                instrument_token=instrument_token,
                buy_price=price,
                quantity=quantity,
                buy_time=datetime.now().isoformat()
            )
            self.portfolio_db.insert(stock_entry.dict())
            return result

        logger.error("Trade failed for %s: %s", symbol, result)
        raise OrderPlacementException(f"Trade failed: {result}")