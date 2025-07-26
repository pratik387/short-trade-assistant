# @role: Handles exit evaluation and trade execution
# @used_by: exit_job_runner, backtests, CLI
# @tags: exit, decision, execution

from datetime import datetime, timedelta
import pandas as pd
from typing import Dict
from pytz import timezone as pytz_timezone
from config.logging_config import get_loggers
from services.technical_analysis_exit import evaluate_exit
from util.diagnostic_report_generator import diagnostics_tracker
from exceptions.exceptions import OrderPlacementException
from services.indicator_enrichment_service import enrich_with_indicators
from services.technical_analysis import calculate_score
from util.util import calculate_dynamic_exit_threshold
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
        if self.config.get("profit_target_escalation").get("enabled", False):
            pnl_threshold = self.config["profit_target_escalation"].get("pnl_threshold", 1.0)
            macd_threshold = self.config["profit_target_escalation"].get("macd_threshold", 20)
            macd_val = df["MACD"].iloc[-1] if "MACD" in df.columns else 0
            close = df["close"].iloc[-1]
            cost_basis = entry_price
            pnl = ((close - cost_basis) / cost_basis) * 100 if cost_basis else 0
            if macd_val >= macd_threshold and pnl >= pnl_threshold:
                self.config["profit_target_exit"]["profit_target_pct"] *= 1.1

        # 🛑 1. ATR Stop Loss Exit (replaces fixed stop loss)
        days_held = (current_date - entry_time).days
        if days_held >= self.config.get("minimum_holding_days"):
            triggered, reason_text = self._check_atr_stop_loss(df, entry_price, self.config, symbol)
            if triggered:
                return self._build_exit_result(df, stock, current_date, reason="atr_stop_loss") | {
                    "note": reason_text,
                    "reasons": [
                        {"filter": "atr_stop_loss", "weight": 0, "reason": reason_text}
                    ],
                    "breakdown": [("atr_stop_loss", 0, reason_text)]
                }

        # 🔥 2. Early Profit Exit
        early_exit_result = self.check_early_exit_on_profit(stock, df, symbol, current_date)
        if early_exit_result and early_exit_result.get("recommendation") == "EXIT":
            return self._build_exit_result(df, stock, current_date, reason="early_profit_exit")


        # 🌟 3. Profit Target Exit
        if self.config.get("profit_target_exit").get("enabled", True):
            profit_pct = self.config["profit_target_exit"].get("profit_target_pct", 0.02)
            if df["close"].iloc[-1] >= entry_price * (1 + profit_pct):
                return self._build_exit_result(df, stock, current_date, reason="profit_target")

        # 📈 4. Trailing ATR Stop
        if self.config.get("trailing_stop").get("enabled", True):
            lookback = self.config["trailing_stop"].get("lookback_days", 10)
            atr_multiplier = self.config["trailing_stop"].get("atr_multiplier", 3)
            if "ATR" in df.columns and len(df) >= lookback:
                atr = df["ATR"].iloc[-1]
                highest = df["close"].iloc[-lookback:].max()
                trailing_sl = highest - atr * atr_multiplier
                if df["close"].iloc[-1] <= trailing_sl:
                    return self._build_exit_result(df, stock, current_date, reason="trailing_atr")


         # 🧐 5. Filter-based Exit
        result = evaluate_exit(df, entry_price, entry_time, current_date, self.config, symbol)
        dynamic_threshold = calculate_dynamic_exit_threshold(
            config=self.config,
            df=df,
            days_held=days_held
        )

        score = result["score"]
        raw_reasons = result["raw_reasons"]
        logger.debug(f"[DYNAMIC THRESHOLD] {symbol} | Days Held: {days_held}, Threshold: {dynamic_threshold:.2f}, Score: {score}")

        reduced_threshold = dynamic_threshold * 0.75
        logger.info(f"[EXIT CHECK] {symbol} | Score: {score:.2f} | Threshold: {dynamic_threshold:.2f} | Reduced: {reduced_threshold:.2f}")

        if score >= reduced_threshold:
            return self._build_exit_result(df, stock, current_date, reason="🔁 exit filters triggered") | {
                "score": score,
                "reasons": raw_reasons,
                "breakdown": [(r["filter"], r["weight"], r["reason"]) for r in raw_reasons],
            }

        # 🧐 6. Score Collapse with Filter Loss Logic
        if self.config.get("core_filter_loss_exit", {}).get("enabled", False):
            decision = self.evaluate_score_collapse_impact(df, stock["symbol"], stock, current_date)
            if decision == "EXIT":
                return self._build_exit_result(df, stock, current_date, reason="score_collapse_and_filter_loss")
            elif decision == "REDUCE":
                return self._build_exit_result(df, stock, current_date, reason="score_collapse_reduce_treated_as_exit")

        return self._build_hold_result(df, stock, current_date, raw_reasons, score)

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
                score_before=stock.get("score", 0),
                score_after=result.get("entry_score_at_exit", 0),
                entry_score_drop=result.get("entry_score_drop", 0),
                entry_score_drop_pct=result.get("entry_score_drop_pct", 0)
            )

            trade_logger.info(f"✅ Exited {symbol} at ₹{exit_price:.2f} | PnL: Rs. {result['pnl']:.2f} | PnL %: {result['pnl_percent']:.2f}% | Reason: {reason_summary}")

        except OrderPlacementException as e:
            logger.warning(f"❌ Order placement failed for {stock['symbol']}: {e}")

    def _build_exit_result(self, df, stock, current_date, reason=""):
        symbol = stock["symbol"]
        entry_price = stock["entry_price"]
        entry_time = stock["entry_date"]
        current_price = df["close"].iloc[-1]
        pnl = current_price - entry_price
        pnl_percent = (pnl / entry_price) * 100
        days_held = (current_date - entry_time).days

        latest = df.iloc[-1]
        avg_rsi = df["RSI"].rolling(14).mean().iloc[-1]

        entry_score_at_exit, _ = calculate_score(latest, self.config, avg_rsi, symbol=symbol)
        entry_score = stock.get("score", 0) if isinstance(stock, dict) else 0
        entry_score_drop = entry_score - entry_score_at_exit
        entry_score_drop_pct = round((entry_score_drop / entry_score) * 100, 2) if entry_score else 0

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
            "exit_date": str(current_date),
            "entry_score_at_exit": entry_score_at_exit,
            "entry_score_drop": entry_score_drop,
            "entry_score_drop_pct": entry_score_drop_pct,
            "reasons": [
                {
                    "filter": reason,
                    "weight": 0,
                    "reason": f"Hard exit: {reason}"
                }
            ],
            "breakdown": [(reason, 0, f"Hard exit: {reason}")]
        }
    
    def _build_hold_result(self, df, stock, current_date, raw_reasons, score):
        symbol = stock["symbol"]
        entry_price = stock["entry_price"]
        current_price = df["close"].iloc[-1]
        pnl = current_price - entry_price
        pnl_percent = (pnl / entry_price) * 100
        days_held = (current_date - stock["entry_date"]).days

        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_percent": round(pnl_percent, 2),
            "pnl": round(pnl, 2),
            "days_held": days_held,
            "recommendation": "HOLD",
            "exit_reason": "score_below_threshold",
            "score": score,
            "reasons": raw_reasons,
            "breakdown": [(r["filter"], r["weight"], r["reason"]) for r in raw_reasons]
        }

    def _check_atr_stop_loss(self, df: pd.DataFrame, entry_price: float, config: dict, symbol: str = "") -> tuple[bool, str]:
        try:
            exit_cfg = config.get("stop_loss_exit", {})
            if not exit_cfg.get("enabled", False):
                return False, ""

            close = df["close"].iloc[-1]
            triggered = False
            reason = ""

            if exit_cfg.get("use_atr", False) and "ATR" in df.columns:
                atr_multiplier = exit_cfg.get("atr_multiplier", 1.5)
                atr = df["ATR"].iloc[-1]
                sl_price = entry_price - (atr_multiplier * atr)
                if close <= sl_price:
                    reason = f"ATR SL hit: Close={close:.2f}, SL={sl_price:.2f}, ATR={atr:.2f}, Mult={atr_multiplier}"
                    triggered = True

            if not triggered and "stop_loss_pct" in exit_cfg:
                sl_pct = exit_cfg["stop_loss_pct"]
                hard_sl = entry_price * (1 - sl_pct)
                if close <= hard_sl:
                    reason = f"Fixed SL hit: Close={close:.2f}, SL={hard_sl:.2f}, Threshold={sl_pct*100:.2f}%"
                    triggered = True

            if triggered:
                logger.info(f"🛑 {symbol} triggered Stop Loss: {reason}")
                return True, reason

            return False, ""

        except Exception as e:
            logger.exception(f"❌ Error in stop loss logic for {symbol}: {e}")
            return False, ""
    
    def check_early_exit_on_profit(self, position, df, symbol, current_date):
        days_held = (current_date - position["entry_date"]).days
        pnl = ((df['close'].iloc[-1] - position["entry_price"]) / position["entry_price"]) * 100
        threshold = 5.0

        if pnl >= threshold:
            macd = df["MACD"].iloc[-1] if "MACD" in df.columns and pd.notna(df["MACD"].iloc[-1]) else 0
            rsi = df["RSI"].iloc[-1] if "RSI" in df.columns and pd.notna(df["RSI"].iloc[-1]) else 50
            bb = df["%B"].iloc[-1] if "%B" in df.columns and pd.notna(df["%B"].iloc[-1]) else 0

            macd_ok = macd < 20
            rsi_overbought = rsi > 70
            near_upper_band = bb > 0.95

            if days_held <= 5 and (macd_ok or rsi_overbought or near_upper_band or pnl >= (threshold + 1.5)):
                logger.info(f"Early exit: {symbol} | Days={days_held}, PnL={pnl:.2f}%, MACD={macd}, RSI={rsi}, %B={bb}")
                return self._build_exit_result(df, position, current_date, reason="early_profit_exit")
            else:
                logger.info(f"⚠️ Skipping early exit for {symbol} | Days={days_held}, PnL={pnl:.2f}% — too late or weak signals")

        return None


    def evaluate_score_collapse_impact(self, df: pd.DataFrame, stock: str, position: Dict, current_date: datetime) -> str:
        cfg = self.config.get("core_filter_loss_exit", {})
        if not cfg.get("enabled", False):
            return "HOLD"

        min_hold_days = cfg.get("min_hold_days", 1)
        drop_threshold = cfg.get("score_drop_pct", 60)
        core_filters = set(cfg.get("core_filters", []))

        days_held = (current_date - position["entry_date"]).days
        if days_held < min_hold_days:
            return "HOLD"

        entry_score = position.get("score", 0)
        final_score = position.get("final_score", 0)
        if entry_score == 0:
            return "HOLD"

        score_drop_pct = ((entry_score - final_score) / entry_score) * 100
        if score_drop_pct < drop_threshold:
            return "HOLD"

        # Check if any core filter is still active
        filters = position.get("filters", [])
        active_filters = {f[0] for f in filters if isinstance(f, list) and f[1] > 0}
        core_active = core_filters.intersection(active_filters)

        if core_active:
            return "HOLD"

        # Structural break logic
        try:
            swing_lookback = cfg.get("swing_lookback", 3)
            recent_lows = df[df["date"] <= current_date].tail(swing_lookback)["low"]
            swing_low = recent_lows.min()
            latest_price = df[df["date"] == current_date]["close"].values[0]

            if latest_price < swing_low:
                return "EXIT"
            else:
                return "REDUCE"
        except Exception:
            return "EXIT"


