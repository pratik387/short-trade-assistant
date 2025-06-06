import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ExitService:
    def __init__(self, config, portfolio_db, data_provider, notifier=None, blocked_logger=None):
        self.config = config
        self.portfolio_db = portfolio_db
        self.data_provider = data_provider
        self.notifier = notifier
        self.blocked_logger = blocked_logger

        self.atr_multiplier = config.get("atr_multiplier", 3)
        self.exit_strategy = config.get("exit_strategy", {})
        self.criteria = config.get("exit_criteria", {})
        self.use_adx_macd = self.exit_strategy.get("use_adx_macd_confirmation", False)
        self.fallback_exit = self.exit_strategy.get("fallback_exit_if_data_missing", True)
        self.log_blocked = self.exit_strategy.get("log_blocked_exits", True)

    def check_exits(self):
        records = self.portfolio_db.all()
        for stock in records:
            df = self.data_provider.fetch_exit_data(stock)
            if df is None or df.empty:
                continue
            current_price = df["close"].iloc[-1]
            actions = self._evaluate_exit(stock, current_price, df)
            for action in actions:
                logger.info(f"{action['reason']} for {stock['symbol']} at price {current_price:.2f}")
                if self.notifier:
                    self.notifier(stock["symbol"], current_price)
                self.portfolio_db.remove(self.portfolio_db.query().symbol == stock["symbol"])

    def _evaluate_exit(self, stock, current_price, df):
        actions = []
        buy_price = stock["close"]
        targets = self.exit_strategy.get("targets", [])
        percentages = self.exit_strategy.get("percentages", [])
        trail_pct = self.exit_strategy.get("trailing_stop_percent", 1.5)

        sold = stock.get("sold_targets", [])
        quantity = stock.get("quantity", 1)
        highest = max(stock.get("highest_price", buy_price), current_price)
        stock["highest_price"] = highest

        allow_exit, reason_blocked = self._adx_macd_gate(df)
        if not allow_exit:
            allow_exit, override_reason = self._check_overrides(df)
            reason_blocked += f" {override_reason}" if override_reason else ""

        if not allow_exit:
            message = f"[{datetime.now().isoformat()}] Exit blocked for {stock['symbol']}: {reason_blocked}"
            logger.info(message)
            if self.log_blocked and self.blocked_logger:
                self.blocked_logger(message)
            return []

        for i, multiplier in enumerate(targets):
            if i in sold:
                continue
            if current_price >= buy_price * multiplier:
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

        stock["sold_targets"] = sold
        stock["last_checked"] = datetime.now().isoformat()
        self.portfolio_db.update(stock, self.portfolio_db.query().symbol == stock["symbol"])
        return actions

    def _adx_macd_gate(self, df):
        if not self.use_adx_macd:
            return True, ""
        adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
        macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
        macd_signal = df["MACD_Signal"].iloc[-1] if "MACD_Signal" in df.columns else None

        if None in (adx, macd, macd_signal):
            return self.fallback_exit, "Missing ADX or MACD values"
        if adx >= 25 and macd >= macd_signal:
            return False, f"Strong trend (ADX={adx:.2f}, MACD={macd:.2f} > Signal={macd_signal:.2f})"
        return True, ""

    def _check_overrides(self, df):
        reason = ""
        ma_short = self.criteria.get("ma_short", 20)
        ma_long = self.criteria.get("ma_long", 50)
        rsi_lower = self.criteria.get("rsi_lower", 50)

        short_ma = df["close"].rolling(ma_short).mean().iloc[-1]
        long_ma = df["close"].rolling(ma_long).mean().iloc[-1]
        rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else None

        if short_ma < long_ma:
            return True, "MA crossdown override triggered"
        if rsi and rsi < rsi_lower:
            return True, f"RSI dropped below {rsi_lower} (current: {rsi:.2f})"
        return False, ""
