"""
Backtest with capital reuse and fixed ₹20,000 trades.
Stocks are exited on signal or after 10 days.
Capital from exits is reinvested daily.
"""
import sys
from pathlib import Path

# Ensure the root directory is in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import logging
from datetime import datetime, timedelta
from pytz import timezone
from services.entry_service import EntryService
from services.exit_service import ExitService
from brokers.kite.kite_broker import KiteBroker as KiteDataProvider
from backtesting.trade_recorder import TradeRecorder
from backtesting.config import BACKTEST_CONFIG
from config.filters_setup import load_filters
from brokers.kite.kite_broker import KiteBroker
from db.tinydb.client import get_table
from services.notification.email_alert import send_exit_email
from trading.trade_executor import TradeExecutor
from util.util import is_market_active

logger = logging.getLogger("entry_service")


TARGET_PER_TRADE = 20000
MAX_TRADES_PER_DAY = 5
MAX_HOLD_DAYS = 10

def run_backtest():
    config = load_filters()
    
    broker = KiteBroker()
    entry_service = EntryService(broker, config, "nifty_500")

    portfolio_db = get_table("portfolio")
    trade_executor = TradeExecutor(broker=broker)

    # Notifier: email alerts
    def notifier(symbol: str, price: float):
        try:
            send_exit_email(symbol, price)
            logger.info(f"📧 Sent exit email for {symbol} at {price}")
        except Exception as e:
            logger.exception(f"❌ Failed to send exit email for {symbol}: {e}")

    # Blocked logger: log failures to file
    def blocked_logger(message: str):
        try:
            path = Path(__file__).resolve().parent.parent / "logs" / "blocked_exits.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - {message}\n")
        except Exception:
            logger.exception("Failed to log blocked exit message")

    exit_service = ExitService(
            config=config,
            portfolio_db=portfolio_db,
            data_provider=broker,
            trade_executor=trade_executor,
            notifier=notifier,
            blocked_logger=blocked_logger
        )
    recorder = TradeRecorder()
    provider = KiteDataProvider()

    capital = BACKTEST_CONFIG["capital"]
    open_positions = {}

    start_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["start_date"], "%Y-%m-%d"))
    end_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["end_date"], "%Y-%m-%d"))

    current_date = start_date.replace(hour=9, minute=30, second=0)

    while current_date <= end_date:
        print(f"📅 Processing {current_date.strftime('%Y-%m-%d')} | Available capital: ₹{capital:.2f}")

        current_check_time = current_date.replace(hour=9, minute=30)
        if not is_market_active(current_check_time):
            current_date += timedelta(days=1)
            continue

        # Exit logic
        for symbol in list(open_positions.keys()):
            position = open_positions[symbol]
            buy_date = position["entry_date"]
            df = provider.fetch_candles(symbol, interval="day",  from_date=start_date, to_date=end_date)
            if df is None or len(df) < 2:
                continue

            df = df[df.index <= current_date]
            if len(df) < 2:
                continue

            result = exit_service.evaluate_exit_filters(symbol, position["entry_price"], buy_date)
            allow_exit = result["recommendation"] == "EXIT"
            days_held = (current_date - buy_date).days

            if allow_exit or days_held >= MAX_HOLD_DAYS:
                exit_price = df.iloc[-1]["close"]
                qty = position["qty"]
                capital += qty * exit_price
                logger.info(f"💸 Exiting {symbol} | Qty: {qty} | Exit Price: ₹{exit_price:.2f} | P&L: ₹{(qty * exit_price - position['qty'] * position['entry_price']):.2f}")
                recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                del open_positions[symbol]

        # Entry logic
        if capital >= TARGET_PER_TRADE:
            suggestions = entry_service.get_suggestions()
            top_picks = sorted(suggestions, key=lambda x: x.get("score", 0), reverse=True)

            for pick in top_picks:
                if len(open_positions) >= MAX_TRADES_PER_DAY:
                    break

                symbol = pick["symbol"]
                if symbol in open_positions:
                    continue

                df = provider.fetch_candles(symbol, interval="day",  from_date=start_date, to_date=end_date)
                if df is None or len(df) < 2:
                    continue
                df = df[df.index <= current_date]
                if len(df) < 2:
                    continue

                entry_date = df.index[-2]
                entry_price = df.iloc[-2]["close"]
                qty = int(TARGET_PER_TRADE // entry_price)
                if qty == 0:
                    continue

                invested = qty * entry_price
                capital -= invested

                open_positions[symbol] = {
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "qty": qty
                }
                logger.info(f"🛒 Buying {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f}")
                recorder.record_entry(symbol, entry_date.strftime("%Y-%m-%d"), entry_price, invested)

        current_date += timedelta(days=1)
        current_date = current_date.replace(hour=9, minute=30, second=0)

    recorder.export_csv()
    print("✅ Backtest finished. Final capital: ₹{:.2f}".format(capital))

if __name__ == "__main__":
    run_backtest()
