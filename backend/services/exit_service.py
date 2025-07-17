# @role: Handles exit evaluation and trade execution
# @used_by: exit_job_runner, backtests, CLI
# @tags: exit, decision, execution

from datetime import datetime, timedelta
import pandas as pd
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers
from services.technical_analysis_exit import evaluate_exit
from util.diagnostic_report_generator import diagnostics_tracker
from exceptions.exceptions import OrderPlacementException
from services.indicator_enrichment_service import enrich_with_indicators
india_tz = pytz_timezone("Asia/Kolkata")
logger, trade_logger = get_loggers()

class ExitService:
    def __init__(self, config, portfolio_db, data_provider, notifier=None):
        self.config = config
        self.portfolio_db = portfolio_db
        self.data_provider = data_provider
        self.notifier = notifier

    def evaluate_exit_decision(self, stock, current_date=None, df: pd.DataFrame = None):
        symbol = stock["symbol"]
        entry_price = stock["entry_price"]
        entry_time = stock["entry_date"]
        current_date = current_date or datetime.now(india_tz)
        if df is None:
            # Real-time trading mode
            lookback_days = self.config.get("exit_lookback_days", 30)
            from_date = current_date - timedelta(days=lookback_days)
            df = self.data_provider.fetch_candles(
                symbol=symbol,
                interval="day",
                from_date=from_date,
                to_date=current_date
            )
        else:
            df = df.copy()
        if df.index.name == 'date':
            df.reset_index(inplace=True)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_index()
        df = df[df["date"] <= current_date] 
        df = enrich_with_indicators(df)

        # 🎯 Profit Target Escalation Logic
        if self.config.get("profit_target_escalation", {}).get("enabled", False):
            pnl_threshold = self.config["profit_target_escalation"].get("pnl_threshold", 1.0)
            macd_threshold = self.config["profit_target_escalation"].get("macd_threshold", 20)
            macd_val = df["MACD"].iloc[-1] if "MACD" in df.columns else 0
            close = df["close"].iloc[-1]
            cost_basis = entry_price
            pnl = ((close - cost_basis) / cost_basis) * 100 if cost_basis else 0
            logger.info(f"[ESCALATION] {symbol} | MACD={macd_val:.2f}, PnL={pnl:.2f}%")
            if macd_val >= macd_threshold and pnl >= pnl_threshold:
                self.config["profit_target_exit"]["profit_target_pct"] *= 1.1  # example bump

        # 📉 1. Stop Loss Exit
        if self.config.get("stop_loss_exit", {}).get("enabled", True):
            stop_loss_pct = self.config["stop_loss_exit"].get("stop_loss_pct", 0.01)
            if df["close"].iloc[-1] <= entry_price * (1 - stop_loss_pct):
                return self._build_exit_result(df, symbol, entry_price, entry_time, current_date, reason="stop_loss")

        # 🎯 2. Profit Target Exit
        if self.config.get("profit_target_exit", {}).get("enabled", True):
            profit_pct = self.config["profit_target_exit"].get("profit_target_pct", 0.02)
            if df["close"].iloc[-1] >= entry_price * (1 + profit_pct):
                return self._build_exit_result(df, symbol, entry_price, entry_time, current_date, reason="profit_target")

        # 📈 3. Trailing ATR Stop
        if self.config.get("trailing_stop", {}).get("enabled", True):
            lookback = self.config["trailing_stop"].get("lookback_days", 10)
            atr_multiplier = self.config["trailing_stop"].get("atr_multiplier", 3)
            if "ATR" in df.columns and len(df) >= lookback:
                atr = df["ATR"].iloc[-1]
                highest = df["close"].iloc[-lookback:].max()
                trailing_sl = highest - atr * atr_multiplier
                if df["close"].iloc[-1] <= trailing_sl:
                    return self._build_exit_result(df, symbol, entry_price, entry_time, current_date, reason="trailing_atr")


        # 🧠 4. Filter-based Exit
        result = evaluate_exit(df, entry_price, entry_time, current_date, self.config, symbol)
        if result["recommendation"] == "EXIT":
             return self._build_exit_result(df, symbol, entry_price, entry_time, current_date, reason="🔁 exit filters triggered") | {
                "score": result["score"],
                "reasons": result["raw_reasons"],
                "breakdown": [(r["filter"], r["weight"], r["reason"]) for r in result["raw_reasons"]],
    }

        return result  # HOLD

    def execute_exit(self, stock, result, current_date=None):
        try:
            current_date = current_date or datetime.now(india_tz)
            qty = stock["qty"]
            symbol = stock["symbol"]
            exit_price = result["current_price"]
            reason_summary = result["exit_reason"]

            self.data_provider.place_order(
                symbol=symbol,
                quantity=qty,
                action="sell",
                price=exit_price,
                order_type="MARKET",
                timestamp=current_date
            )

            diagnostics_tracker.record_exit(
                symbol=symbol,
                exit_time=str(current_date),
                exit_price=exit_price,
                pnl=result["pnl"],
                pnl_percent=result["pnl_percent"],
                reason=reason_summary,
                exit_filters=result.get("breakdown"),
                indicators=result.get("breakdown"),
                days_held=result.get("days_held"),
                score_before=result.get("score", 0),
                score_after=result.get("score", 0),
            )

            trade_logger.info(f"✅ Exited {symbol} at ₹{exit_price:.2f} | PnL: Rs. {result['pnl']:.2f} | PnL %: {result['pnl_percent']:.2f}% | Reason: {reason_summary}")

        except OrderPlacementException as e:
            logger.warning(f"❌ Order placement failed for {stock['symbol']}: {e}")

    def _build_exit_result(self, df, symbol, entry_price, entry_time, current_date, reason=""):
        current_price = df["close"].iloc[-1]
        pnl = current_price - entry_price
        pnl_percent = (pnl / entry_price) * 100
        days_held = (current_date - entry_time).days

        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": round(pnl_percent, 2),
            "pnl": round(pnl, 2),
            "days_held": days_held,
            "recommendation": "EXIT",
            "exit_reason": reason,
            "score": 0,
            "reasons": [
                {
                    "filter": reason,
                    "weight": 0,
                    "reason": f"Hard exit: {reason}"
                }
            ],
            "breakdown": [(reason, 0, f"Hard exit: {reason}")]
        }
