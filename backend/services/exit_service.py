# exit_service.py — Exit signal evaluation and trade handling

from datetime import datetime
from typing import Optional
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers
from exceptions.exceptions import OrderPlacementException
from services.technical_analysis_exit import prepare_exit_indicators, apply_exit_filters
from util.diagnostic_report_generator import diagnostics_tracker

agent_logger, trade_logger = get_loggers()
india_tz = pytz_timezone("Asia/Kolkata")

class ExitService:
    def __init__(self, config, portfolio_db, data_provider, notifier=None):
        self.config = config
        self.portfolio_db = portfolio_db
        self.data_provider = data_provider
        self.notifier = notifier

    def evaluate_exit_filters(self, symbol: str, entry_price: float, entry_time: datetime, current_date: datetime, entry_score: Optional[int] = 0) -> dict:
        df = self.data_provider.fetch_candles(symbol=symbol, interval="day", days=30)
        df = prepare_exit_indicators(df, symbol)
        current_price = df["close"].iloc[-1]
        pnl_percent = round(((current_price - entry_price) / entry_price) * 100, 2)
        days_held = (current_date - entry_time).days

        allow_exit, reasons, breakdown = apply_exit_filters(
            df,
            entry_price,
            entry_time,
            current_date,
            self.config.get("exit_criteria", {}),
            self.config.get("fallback_exit_if_data_missing", True),
            symbol=symbol
        )

        # Adaptive Trailing Stop Loss Logic
        atr = df["atr"].iloc[-1] if "atr" in df.columns else 0
        factor = self.config.get("exit_strategy", {}).get("trailing_atr_factor", 1.5)
        highest_price = max(df["close"][-10:])  # past 10 days
        trailing_stop = highest_price - atr * factor
        trailing_exit_triggered = current_price <= trailing_stop

        if trailing_exit_triggered and not allow_exit:
            trailing_reason = {
                "filter": "atr_trailing_stop",
                "weight": 10,
                "reason": f"Trailing SL hit | Current: ₹{current_price}, SL: ₹{trailing_stop:.2f}, ATR={atr:.2f}, Factor={factor}"
            }
            reasons.append(trailing_reason)
            breakdown.append((
                trailing_reason["filter"],
                trailing_reason["weight"],
                trailing_reason["reason"]
            ))
            allow_exit = True

        score_drop_pct = self.config.get("exit_criteria", {}).get("score_drop_threshold_percent", 40)
        initial_score = sum(r["weight"] for r in reasons)
        score_drop = 0

        if entry_score > 0 and initial_score < entry_score:
            score_drop = ((entry_score - initial_score) / entry_score) * 100
            if score_drop >= score_drop_pct:
                reasons.append({
                    "filter": "score_drop",
                    "weight": 10,
                    "reason": f"Score dropped by {score_drop:.1f}% (from {entry_score} to {initial_score})"
                })
                breakdown.append(("score_drop", 10, f"Score dropped {score_drop:.1f}%"))
                allow_exit = True

        result = {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": pnl_percent,
            "days_held": days_held,
            "recommendation": "EXIT" if allow_exit else "HOLD",
            "initial_score": initial_score,
            "final_score": entry_score,
            "score_drop": score_drop,
            "reasons": reasons,
            "atr": atr,
            "breakdown": breakdown
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
                result = self.evaluate_exit_filters(
                    stock["symbol"],
                    stock["entry_price"],
                    stock["buy_time"],
                    datetime.now(india_tz),
                    entry_score=stock.get("entry_score", 0)
                )
                if result["recommendation"] == "EXIT":
                    self.execute_exit(stock, result, current_date=datetime.now(india_tz))
            except Exception as e:
                agent_logger.warning(f"❌ Exit check failed for {stock['symbol']}: {e}")

    def execute_exit(self, stock, result, current_date: Optional[datetime] = None):
        try:
            qty = stock["qty"]
            symbol = stock["symbol"]
            entry_price = stock["entry_price"]
            exit_price = result["current_price"]
            score_before = result["initial_score"]
            score_after = result["final_score"]
            reason_summary = ", ".join([r['filter'] for r in result['reasons']])

            exit_time = current_date or datetime.now(india_tz)

            diagnostics_tracker.record_exit(
                symbol=symbol,
                exit_time=str(exit_time),
                exit_price=exit_price,
                pnl=result["pnl_percent"],
                reason=reason_summary,
                exit_filters=[(r["filter"], r["weight"], r["reason"]) for r in result.get("reasons", [])],
                indicators=result.get("breakdown"),
                days_held=result.get("days_held", 0),
                score_before=score_before,
                score_after=score_after
            )

            self.data_provider.place_order(
                symbol=symbol,
                quantity=qty,
                action="sell",
                price=exit_price,
                order_type="MARKET",
                timestamp=exit_time
            )

            trade_logger.info(f"✅ Exiting {symbol} at ₹{exit_price} | PnL: {result['pnl_percent']}% | Reasons: {reason_summary}")

        except OrderPlacementException as e:
            agent_logger.warning(f"❌ Order placement failed for {stock['symbol']}: {e}")
