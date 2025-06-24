# exit_service.py — Exit signal evaluation and trade handling

from datetime import datetime
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers
from exceptions.exceptions import OrderPlacementException
from services.technical_analysis_exit import prepare_exit_indicators, apply_exit_filters

agent_logger, trade_logger = get_loggers()
india_tz = pytz_timezone("Asia/Kolkata")

class ExitService:
    def __init__(self, config, portfolio_db, data_provider, trade_executor, notifier=None):
        self.config = config
        self.portfolio_db = portfolio_db
        self.data_provider = data_provider
        self.trade_executor = trade_executor
        self.notifier = notifier

    def evaluate_exit_filters(self, symbol: str, entry_price: float, entry_time: datetime) -> dict:
        df = self.data_provider.fetch_candles(symbol=symbol, interval="day", days=30)
        df = prepare_exit_indicators(df)
        current_price = df["close"].iloc[-1]
        pnl_percent = round(((current_price - entry_price) / entry_price) * 100, 2)
        days_held = (datetime.now(india_tz) - entry_time).days

        allow_exit, reasons = apply_exit_filters(df, entry_price, entry_time, self.config.get("exit_criteria", {}), self.config.get("fallback_exit_if_data_missing", True), symbol=symbol)

        result = {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": pnl_percent,
            "days_held": days_held,
            "recommendation": "EXIT" if allow_exit else "HOLD",
            "initial_score": sum(r["weight"] for r in reasons),
            "final_score": sum(r["weight"] for r in reasons),
            "score_drop": 0,
            "reasons": reasons
        }
        self.log_exit_decision(symbol, result)
        return result

    def log_exit_decision(self, symbol, result):
        agent_logger.info(f"📉 Exit Decision for {symbol} | Score {result['initial_score']} → {result['final_score']} (Drop: {result['score_drop']})")
        for reason in result["reasons"]:
            agent_logger.info(f"    🧮 {reason['filter']}: -{reason['weight']} | {reason['reason']}")

    def check_exits(self):
        agent_logger.info("Running check_exits on portfolio")
        for stock in self.portfolio_db.all():
            try:
                result = self.evaluate_exit_filters(stock["symbol"], stock["buy_price"], stock["buy_time"])
                if result["recommendation"] == "EXIT":
                    self.execute_exit(stock, result)
            except Exception as e:
                agent_logger.warning(f"❌ Exit check failed for {stock['symbol']}: {e}")

    def execute_exit(self, stock, result):
        try:
            self.trade_executor.execute_trade(
                symbol=stock["symbol"],
                instrument_token=stock.get("instrument_token"),
                quantity=stock["quantity"],
                action="sell",
                price=result["current_price"],
                order_type="MARKET"
            )
            trade_logger.info(f"✅ Exiting {stock['symbol']} at ₹{result['current_price']} | PnL: ₹{result['pnl_percent']}% | Reason: {result['reasons']}")
            if self.notifier:
                self.notifier(stock["symbol"], result["current_price"])
        except OrderPlacementException as e:
            agent_logger.warning(f"❌ Order placement failed for {stock['symbol']}: {e}")
