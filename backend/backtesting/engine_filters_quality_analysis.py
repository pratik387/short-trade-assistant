import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Imports
from datetime import datetime, timedelta
from pytz import timezone
from services.entry_service import EntryService
from services.exit_service import ExitService
from brokers.mock.mock_broker import MockBroker
from backtesting.trade_recorder import TradeRecorder
from backtesting.config import BACKTEST_CONFIG
from config.filters_setup import load_filters
from db.tinydb.client import get_table
from trading.trade_executor import TradeExecutor
from util.util import is_market_active
from config.logging_config import get_loggers, switch_agent_log_file

# Trading parameters
PROFIT_TARGET = BACKTEST_CONFIG["profit_target"]
STOP_LOSS_THRESHOLD = BACKTEST_CONFIG["stop_loss_threshold"]
MIN_ENTRY_SCORE = BACKTEST_CONFIG["minimum_entry_score"]

logger, trade_logger = get_loggers()

def run_quality_analysis():
    config = load_filters()
    broker = MockBroker(use_cache=True)
    broker.get_ltp = lambda symbol: {symbol: broker.fetch_candles(symbol, interval="day").iloc[-1]["close"]}

    entry_service = EntryService(broker, config, "all")
    portfolio_db = get_table("portfolio")
    trade_executor = TradeExecutor(broker=broker)
    exit_service = ExitService(config=config, portfolio_db=portfolio_db, data_provider=broker, trade_executor=trade_executor)
    recorder = TradeRecorder()

    capital = BACKTEST_CONFIG["capital"]
    open_positions = {}

    start_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["start_date"], "%Y-%m-%d"))
    end_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["end_date"], "%Y-%m-%d"))
    current_date = start_date.replace(hour=9, minute=30, second=0)
    last_logged_month = None

    try:
        while current_date <= end_date:
            month_str = current_date.strftime("%Y-%m")
            if month_str != last_logged_month:
                switch_agent_log_file(month_str)
                last_logged_month = month_str
            logger.info(f"🗕️ Processing {current_date.strftime('%Y-%m-%d')} | Open Positions: {len(open_positions)}")

            if not is_market_active(current_date):
                current_date += timedelta(days=1)
                continue

            # Exit logic for current holdings
            for symbol in list(open_positions.keys()):
                position = open_positions[symbol]
                buy_date = position["entry_date"]
                df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
                if df is None or len(df) < 2:
                    continue
                df = df[df.index <= current_date]
                if len(df) < 2:
                    continue

                entry_price = position["entry_price"]
                current_close = df.iloc[-1]["close"]
                day_low = df.iloc[-1]["low"]
                stop_loss_price = entry_price * (1 + STOP_LOSS_THRESHOLD / 100)
                days_held = (current_date - buy_date).days

                result = exit_service.evaluate_exit_filters(symbol, entry_price, buy_date, current_date=current_date)
                allow_exit = result["recommendation"] == "EXIT"
                trigger_exit = False
                reason = "exit signal"
                exit_price = current_close

                if (day_low <= stop_loss_price and days_held == 0):
                    reason = f"🔑 stop-loss hit intraday (low: ₹{day_low:.2f} <= SL ₹{stop_loss_price:.2f})"
                    exit_price = stop_loss_price
                    trigger_exit = True
                elif (day_low <= stop_loss_price):
                    reason = f"🔑 stop-loss hit (low: ₹{day_low:.2f} <= SL ₹{stop_loss_price:.2f})"
                    exit_price = stop_loss_price
                    trigger_exit = True
                elif ((current_close - entry_price) / entry_price) * 100 >= PROFIT_TARGET:
                    reason = f"💰 profit target hit ({((current_close - entry_price) / entry_price) * 100:.2f}%)"
                    trigger_exit = True
                elif allow_exit:
                    reason = "🔁 exit filters triggered"
                    trigger_exit = True

                if trigger_exit:
                    qty = position["qty"]
                    capital += qty * exit_price
                    pnl = qty * (exit_price - entry_price)
                    logger.info(f"✅ Exiting {symbol} at ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} | Reason: {reason}")
                    trade_logger.info(f"EXIT | {symbol} | Qty: {qty} | Entry: ₹{entry_price:.2f} | Exit: ₹{exit_price:.2f} | PnL: ₹{pnl:.2f}\n{reason}")
                    recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                    del open_positions[symbol]

            # Entry logic with no limits — buy 1 share only
            suggestions = entry_service.get_suggestions()
            top_picks = sorted([s for s in suggestions if s.get("score", 0) >= MIN_ENTRY_SCORE], key=lambda x: x.get("score", 0), reverse=True)

            for pick in top_picks:
                symbol = pick["symbol"]
                score = pick.get("score", 0)
                if symbol in open_positions:
                    continue

                df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
                if df is None or len(df) < 2:
                    continue
                df = df[df.index <= current_date]
                if len(df) < 2:
                    continue

                entry_date = df.index[-2]
                entry_price = df.iloc[-2]["close"]
                qty = 1
                invested = qty * entry_price
                capital -= invested

                open_positions[symbol] = {
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "qty": qty,
                    "score": score
                }
                logger.info(f"🛢 Buying {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Entry Score: {score}")
                trade_logger.info(f"ENTRY | {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Score: {score}")
                recorder.record_entry(symbol, entry_date.strftime("%Y-%m-%d"), entry_price, invested)

            current_date += timedelta(days=1)
            current_date = current_date.replace(hour=9, minute=30, second=0)

        # Final exits
        for symbol, pos in open_positions.items():
            df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
            df = df[df.index <= current_date]
            exit_price = df.iloc[-1]["close"]
            capital += pos["qty"] * exit_price
            pnl = pos["qty"] * (exit_price - pos["entry_price"])
            logger.info(f"📤 Force Exit {symbol} | Qty: {pos['qty']} | Exit: ₹{exit_price:.2f} | PnL: ₹{pnl:.2f}")
            trade_logger.info(f"EXIT | {symbol} | Qty: {pos['qty']} | Exit: ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} | Forced exit at end")
            recorder.record_exit(symbol, end_date.strftime("%Y-%m-%d"), exit_price)

        recorder.export_csv()
        logger.info("✅ Backtest finished. Final capital: ₹{:.2f}".format(capital))

    except Exception as e:
        logger.exception(f"Failed: {e}")

if __name__ == "__main__":
    run_quality_analysis()
