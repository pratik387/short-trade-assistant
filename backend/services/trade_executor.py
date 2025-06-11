import json
from datetime import datetime
from pathlib import Path
import logging

from jobs.mock_trade_analyzer import analyze_and_store_pnl
from brokers.base_broker import BaseBroker

logger = logging.getLogger("trade_executor")
logger.setLevel(logging.INFO)

MOCK_TRADES_PATH = Path("backend/mock_trades.json")

class TradeExecutor:
    def __init__(self, mode="mock", broker: BaseBroker = None):
        self.mode = mode
        self.broker = broker

    def execute_trade(self, symbol, quantity, action, price=None):
        logger.info("Executing trade: mode=%s, symbol=%s, qty=%d, action=%s", self.mode, symbol, quantity, action)
        if self.mode == "live":
            return self._execute_live_trade(symbol, quantity, action)
        else:
            return self._record_mock_trade(symbol, quantity, action, price)

    def _execute_live_trade(self, symbol, quantity, action):
        if not self.broker:
            logger.error("Live trade failed: broker not configured")
            raise RuntimeError("No broker configured for live trades")
        try:
            result = self.broker.place_order(symbol, quantity, action)
            logger.info("Live trade executed for %s: %s", symbol, result)
            return result
        except Exception as e:
            logger.exception("Error placing live order for %s", symbol)
            return {"status": "error", "message": str(e)}

    def _record_mock_trade(self, symbol, quantity, action, price=None):
        try:
            MOCK_TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not MOCK_TRADES_PATH.exists():
                with open(MOCK_TRADES_PATH, "w") as f:
                    json.dump([], f)

            with open(MOCK_TRADES_PATH, "r") as f:
                trades = json.load(f)

            mock_price = price if price else 100.0
            trade = {
                "symbol": symbol,
                "action": action.upper(),
                "price": round(mock_price, 2),
                "quantity": quantity,
                "timestamp": datetime.now().isoformat()
            }
            trades.append(trade)

            with open(MOCK_TRADES_PATH, "w") as f:
                json.dump(trades, f, indent=2)

            analyze_and_store_pnl()

            logger.info("[MOCK TRADE] %s", trade)
            return {
                "status": "mocked",
                "symbol": symbol,
                "action": action,
                "price": mock_price
            }

        except Exception as e:
            logger.exception("Error recording mock trade")
            return {"status": "error", "message": str(e)}
