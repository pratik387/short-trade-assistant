# @role: Exit signal evaluation and notification orchestrator
# @used_by: exit_job_runner.py, suggestion_router.py
# @filter_type: logic
# @tags: exit, decision, service
import logging
from datetime import datetime, timezone
from pytz import timezone as pytz_timezone
from util.portfolio_schema import PortfolioStock
from exceptions.exceptions import OrderPlacementException
from services.technical_analysis_exit import prepare_exit_indicators, apply_exit_filters

logger = logging.getLogger(__name__)
india_tz = pytz_timezone("Asia/Kolkata")

class ExitService:
    def __init__(self, config, portfolio_db, data_provider, trade_executor, notifier=None, blocked_logger=None):
        self.config = config
        self.portfolio_db = portfolio_db
        self.data_provider = data_provider
        self.trade_executor = trade_executor
        self.notifier = notifier
        self.blocked_logger = blocked_logger

        self.atr_multiplier = config.get("atr_multiplier", 3)
        self.exit_strategy = config.get("exit_strategy", {})
        self.criteria = config.get("exit_criteria", {})
        self.use_adx_macd = self.exit_strategy.get("use_adx_macd_confirmation", False)
        self.fallback_exit = self.exit_strategy.get("fallback_exit_if_data_missing", True)
        self.log_blocked = self.exit_strategy.get("log_blocked_exits", True)


    def _apply_exit_filters(self, df, entry_price: float, entry_time: datetime, symbol: str) -> tuple[bool, list[str]]:
        return apply_exit_filters(df, entry_price, entry_time, self.criteria, self.fallback_exit, symbol=symbol)

    def evaluate_exit_filters(self, symbol: str, entry_price: float, entry_time: datetime) -> dict:
        df = self.data_provider.fetch_candles(symbol=symbol, interval="day", days=30)
        df = prepare_exit_indicators(df)

        current_price = df["close"].iloc[-1]
        pnl_percent = round(((current_price - entry_price) / entry_price) * 100, 2)

        days_held = (datetime.now(india_tz) - entry_time).days

        allow_exit, reasons = self._apply_exit_filters(df, entry_price, entry_time, symbol=symbol)

        recommendation = "EXIT" if allow_exit else "HOLD"

        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": pnl_percent,
            "days_held": days_held,
            "recommendation": recommendation,
            "exit_reasons": reasons
        }

    def check_exit_for_symbol(self, symbol: str, entry_price: float, entry_time: datetime):
        enriched_symbol = f"{symbol.upper()}.NS"
        df = self.data_provider.fetch_candles(symbol=enriched_symbol, interval="day", days=30)
        if df is None or df.empty:
            return {"status": "No data available", "symbol": symbol}

        df = prepare_exit_indicators(df)
        current_price = df["close"].iloc[-1]
        pnl_percent = round(((current_price - entry_price) / entry_price) * 100, 2)

        days_held = (datetime.now(india_tz) - entry_time).days

        allow_exit, reasons = self._apply_exit_filters(df, entry_price, entry_time, symbol=symbol)

        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": pnl_percent,
            "days_held": days_held,
            "recommendation": "EXIT" if allow_exit else "HOLD",
            "exit_reasons": reasons
        }

    def _evaluate_exit(self, stock_data, current_price, df):
        actions = []
        try:
            stock = PortfolioStock(**stock_data)
        except Exception as ve:
            logger.warning(f"Skipping malformed stock record: {ve}")
            return []

        targets = self.exit_strategy.get("targets", [])
        percentages = self.exit_strategy.get("percentages", [])
        trail_pct = self.exit_strategy.get("trailing_stop_percent", 1.5)

        sold = stock_data.get("sold_targets", [])
        quantity = stock.quantity
        highest = max(stock_data.get("highest_price", stock.buy_price), current_price)
        stock_data["highest_price"] = highest

        allow_exit, reason_blocked = self._apply_exit_filters(df, stock.buy_price, stock.buy_time)

        if not allow_exit:
            message = f"[{datetime.now().isoformat()}] Exit blocked for {stock.symbol}: {'; '.join(reason_blocked)}"
            logger.info(message)
            if self.log_blocked and self.blocked_logger:
                self.blocked_logger(message)
            return []

        for i, multiplier in enumerate(targets):
            if i in sold:
                continue
            if current_price >= stock.buy_price * multiplier:
                qty = int(quantity * percentages[i])
                actions.append({"qty": qty, "reason": f"Target {multiplier}x hit"})
                sold.append(i)

        total_sold = sum([int(quantity * percentages[i]) for i in sold])
        remaining = quantity - total_sold
        trailing_stop = highest * (1 - trail_pct / 100)

        rsi_val = df["RSI"].iloc[-1] if "RSI" in df.columns else None
        rsi_spike = rsi_val and rsi_val > 70 and current_price < df["close"].iloc[-2]

        if remaining > 0:
            if current_price <= trailing_stop:
                actions.append({"qty": remaining, "reason": "Trailing stop hit"})
                sold = list(range(len(targets)))
            elif rsi_spike:
                actions.append({"qty": remaining, "reason": f"RSI spike reversal: RSI={rsi_val:.2f}"})
                sold = list(range(len(targets)))

        stock_data["sold_targets"] = sold
        stock_data["last_checked"] = datetime.now().isoformat()
        self.portfolio_db.update(stock_data, self.portfolio_db.query().symbol == stock.symbol)
        return actions

    def check_exits(self):
        logger.info("Running check_exits on portfolio")
        records = self.portfolio_db.all()
        for stock in records:
            try:
                df = self.data_provider.fetch_candles(symbol=stock["symbol"], interval="day", days=30)
                df = prepare_exit_indicators(df)
                if df is None or df.empty:
                    logger.warning("No exit data for %s", stock['symbol'])
                    continue

                current_price = df["close"].iloc[-1]
                actions = self._evaluate_exit(stock, current_price, df)
                for action in actions:
                    logger.info("%s for %s at price %.2f", action['reason'], stock['symbol'], current_price)

                    try:
                        self.trade_executor.execute_trade(
                            symbol=stock["symbol"],
                            instrument_token=stock.get("instrument_token"),
                            quantity=action["qty"],
                            action="sell",
                            price=current_price,
                            order_type="MARKET"
                        )
                        if self.notifier:
                            self.notifier(stock["symbol"], current_price)
                    except OrderPlacementException as e:
                        logger.warning("Order placement failed for %s: %s", stock["symbol"], str(e))

            except Exception as e:
                logger.exception("Error checking exit for %s: %s", stock.get("symbol", "<unknown>"), e)