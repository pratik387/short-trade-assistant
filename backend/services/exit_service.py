import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
from tinydb import TinyDB, Query

from backend.services.data_fetcher import fetch_kite_data
from backend.services.config import load_filter_config, get_index_symbols
from backend.services.email_alert import send_exit_email

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
PORTFOLIO_PATH = BASE_DIR / "portfolio.json"
BLOCKED_LOG_PATH = BASE_DIR / "blocked_exits.log"

db = TinyDB(str(PORTFOLIO_PATH))
StockQuery = Query()


class ExitService:
    def __init__(self, interval: str = "day", index: str = "all"):
        self.interval = interval
        self.index = index
        self.config = load_filter_config()
        self.atr_multiplier = self.config.get("atr_multiplier", 3)
        self.exit_strategy = self.config.get("exit_strategy", {})
        self.use_adx_macd = self.exit_strategy.get("use_adx_macd_confirmation", False)
        self.fallback_exit = self.exit_strategy.get("fallback_exit_if_data_missing", True)
        self.log_blocked = self.exit_strategy.get("log_blocked_exits", True)

    def check_exits(self):
        portfolio_records = db.all()
        if not portfolio_records:
            logger.info("Portfolio is empty; no exits to check.")
            return

        for rec in portfolio_records:
            symbol = rec.get("symbol")
            buy_price = rec.get("close")
            if symbol is None or buy_price is None:
                logger.warning(f"Skipping invalid portfolio entry: {rec}")
                continue

            token = self._get_token(symbol)
            if token is None:
                logger.warning(f"Instrument token not found for {symbol}; skipping.")
                continue

            df = fetch_kite_data(symbol, token, self.interval, lookback=50)
            if df is None or df.empty:
                logger.error(f"No data for {symbol}; skipping.")
                continue

            # ATR Calculation
            df["tr1"] = df["high"] - df["low"]
            df["tr2"] = (df["high"] - df["close"].shift(1)).abs()
            df["tr3"] = (df["low"] - df["close"].shift(1)).abs()
            df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
            df["atr"] = df["true_range"].rolling(window=14).mean()
            latest_atr = df["atr"].iloc[-1]

            if pd.isna(latest_atr):
                logger.warning(f"Could not compute ATR for {symbol}; skipping.")
                continue

            current_price = df["close"].iloc[-1]
            actions = self._check_hybrid_exit(rec, current_price, buy_price, df)

            for action in actions:
                qty, reason = action["qty"], action["reason"]
                logger.info(f"{reason} for {symbol} at price {current_price:.2f}")
                try:
                    send_exit_email(symbol, current_price)
                except Exception as e:
                    logger.error(f"Error sending email for {symbol}: {e}")

                db.remove(StockQuery.symbol == symbol)
                logger.info(f"{symbol} removed from portfolio after exit.")

    def _check_hybrid_exit(self, stock, current_price, buy_price, df):
        actions = []
        config = self.exit_strategy
        criteria = self.config.get("exit_criteria", {})
        targets = config.get("targets", [])
        percentages = config.get("percentages", [])
        trail_pct = config.get("trailing_stop_percent", 1.5)

        sold = stock.get("sold_targets", [])
        quantity = stock.get("quantity", 1)
        highest = max(stock.get("highest_price", buy_price), current_price)
        stock["highest_price"] = highest

        # Default: allow exit unless ADX+MACD block it
        allow_exit = True
        reason_blocked = ""

        # ADX + MACD Confirmation (if enabled)
        if self.use_adx_macd:
            adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
            macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
            macd_signal = df["MACD_Signal"].iloc[-1] if "MACD_Signal" in df.columns else None

            if None in (adx, macd, macd_signal):
                allow_exit = self.fallback_exit
                if not allow_exit:
                    reason_blocked = "Missing ADX or MACD values"
            elif adx >= 25 and macd >= macd_signal:
                allow_exit = False
                reason_blocked = f"Strong trend (ADX={adx:.2f}, MACD={macd:.2f} > Signal={macd_signal:.2f})"

        # 💡 Override exit block if MA cross or RSI drop triggered
        if not allow_exit:
            ma_short = criteria.get("ma_short", 20)
            ma_long = criteria.get("ma_long", 50)
            use_ma_cross = criteria.get("use_ma_cross", False)

            use_rsi_drop = criteria.get("use_rsi_drop", False)
            rsi_lower = criteria.get("rsi_lower", 50)

            short_ma_val = df["close"].rolling(ma_short).mean().iloc[-1] if use_ma_cross else None
            long_ma_val = df["close"].rolling(ma_long).mean().iloc[-1] if use_ma_cross else None
            rsi_val = df["RSI"].iloc[-1] if use_rsi_drop and "RSI" in df.columns else None

            ma_cross_trigger = (
                use_ma_cross and short_ma_val is not None and long_ma_val is not None and short_ma_val < long_ma_val
            )

            rsi_drop_trigger = (
                use_rsi_drop and rsi_val is not None and rsi_val < rsi_lower
            )

            if ma_cross_trigger:
                allow_exit = True
                reason_blocked += " — MA crossdown override triggered"
            elif rsi_drop_trigger:
                allow_exit = True
                reason_blocked += f" — RSI dropped below {rsi_lower} (current: {rsi_val:.2f})"

        # Log and return if still blocked
        if not allow_exit:
            message = f"[{datetime.now().isoformat()}] Exit blocked for {stock['symbol']}: {reason_blocked}"
            logger.info(message)
            if self.log_blocked:
                with open(BASE_DIR / "blocked_exits.log", "a") as f:
                    f.write(message + "\n")
            return []

        # Target-based exits
        for i, multiplier in enumerate(targets):
            if i in sold:
                continue
            if current_price >= buy_price * multiplier:
                qty = int(quantity * percentages[i])
                actions.append({"qty": qty, "reason": f"Target {multiplier}x hit"})
                sold.append(i)

        # Trailing stop-loss OR RSI spike reversal exit
        total_sold = sum([int(quantity * percentages[i]) for i in sold])
        remaining = quantity - total_sold
        trailing_stop = highest * (1 - trail_pct / 100)

        rsi_val = df["RSI"].iloc[-1] if "RSI" in df.columns else None
        rsi_spike_reversal = (
            rsi_val is not None and rsi_val > 70 and current_price < df["close"].iloc[-2]
        )

        if remaining > 0:
            if current_price <= trailing_stop:
                actions.append({"qty": remaining, "reason": "Trailing stop hit"})
                sold = list(range(len(targets)))
            elif rsi_spike_reversal:
                actions.append({"qty": remaining, "reason": f"RSI spike reversal: RSI={rsi_val:.2f}"})
                sold = list(range(len(targets)))

        stock["sold_targets"] = sold
        stock["last_checked"] = datetime.now().isoformat()
        db.update(stock, StockQuery.symbol == stock["symbol"])
        return actions


    def _get_token(self, symbol: str) -> int:
        instruments = get_index_symbols(self.index)
        for item in instruments:
            if item.get("symbol") == symbol:
                return item.get("instrument_token")
        return None


def run_exit_checks():
    service = ExitService()
    service.check_exits()
