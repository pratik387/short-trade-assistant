"""
Backtest with capital reuse and fixed ₹20,000 trades.
Stocks are exited on signal, profit %, stop-loss %, or after 10 days.
Capital from exits is reinvested daily.
"""
import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Imports
import logging
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

# Create logs directory inside backtesting folder
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file_path = LOG_DIR / "agent.log"

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Trading parameters
TARGET_PER_TRADE = 20000
MAX_TRADES_PER_DAY = 5
MAX_HOLD_DAYS = 10
PROFIT_TARGET = 5.0  # Exit if profit >= 5%
STOP_LOSS_THRESHOLD = -3.0  # Exit if loss <= -3%
MIN_ENTRY_SCORE = 12  # Only enter trades if score >= 12

def run_backtest():
    # Load filters and services
    config = load_filters()
    broker = MockBroker(use_cache=True)  # Use cached OHLCV data from CSV
    entry_service = EntryService(broker, config, "nifty_500")
    portfolio_db = get_table("portfolio")
    trade_executor = TradeExecutor(broker=broker)

    # Initialize services
    exit_service = ExitService(
        config=config,
        portfolio_db=portfolio_db,
        data_provider=broker,
        trade_executor=trade_executor
    )
    recorder = TradeRecorder()

    capital = BACKTEST_CONFIG["capital"]
    open_positions = {}  # Active trades

    # Define backtest period
    start_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["start_date"], "%Y-%m-%d"))
    end_date = timezone("Asia/Kolkata").localize(datetime.strptime(BACKTEST_CONFIG["end_date"], "%Y-%m-%d"))
    current_date = start_date.replace(hour=9, minute=30, second=0)

    # Iterate day by day
    while current_date <= end_date:
        logger.info(f"📅 Processing {current_date.strftime('%Y-%m-%d')} | Available capital: ₹{capital:.2f}")

        if capital < 0:
            logger.warning(f"⚠️ Capital dropped below zero: ₹{capital:.2f}")

        # Skip if market closed
        current_check_time = current_date.replace(hour=9, minute=30)
        if not is_market_active(current_check_time):
            current_date += timedelta(days=1)
            continue

        # Check exit conditions for all open positions
        for symbol in list(open_positions.keys()):
            position = open_positions[symbol]
            buy_date = position["entry_date"]

            # Fetch daily candles for evaluation
            df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
            if df is None or len(df) < 2:
                continue
            df = df[df.index <= current_date]
            if len(df) < 2:
                continue

            # Extract prices
            entry_price = position["entry_price"]
            current_close = df.iloc[-1]["close"]
            day_low = df.iloc[-1]["low"]
            stop_loss_price = entry_price * (1 + STOP_LOSS_THRESHOLD / 100)
            days_held = (current_date - buy_date).days

            # Evaluate exit filters
            result = exit_service.evaluate_exit_filters(symbol, entry_price, buy_date)
            allow_exit = result["recommendation"] == "EXIT"

            # Check for SL/Target/Exit/Max Hold
            trigger_exit = False
            reason = "exit signal"
            exit_price = current_close

            if day_low <= stop_loss_price:
                reason = f"🛑 stop-loss hit intraday (low: ₹{day_low:.2f} <= SL ₹{stop_loss_price:.2f})"
                logger.info(f"⚠️ {symbol} triggered SL | Day Low: ₹{day_low:.2f}, SL Price: ₹{stop_loss_price:.2f}, Entry: ₹{entry_price:.2f}")
                exit_price = stop_loss_price
                trigger_exit = True
            elif ((current_close - entry_price) / entry_price) * 100 >= PROFIT_TARGET:
                reason = f"💰 profit target hit ({((current_close - entry_price) / entry_price) * 100:.2f}%)"
                trigger_exit = True
            elif allow_exit:
                reason = "exit signal"
                trigger_exit = True
            elif days_held >= MAX_HOLD_DAYS:
                reason = f"⏳ max hold days reached ({days_held}d)"
                trigger_exit = True

            # Exit logic
            if trigger_exit:
                qty = position["qty"]
                capital += qty * exit_price
                logger.info(f"✅ Exiting {symbol} at ₹{exit_price:.2f} | PnL: ₹{qty * (exit_price - entry_price):.2f} | Reason: {reason}")
                recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                del open_positions[symbol]

        # Entry logic: select suggestions
        if capital >= TARGET_PER_TRADE:
            suggestions = entry_service.get_suggestions()
            top_picks = sorted(suggestions, key=lambda x: x.get("score", 0), reverse=True)

            for pick in top_picks:
                if len(open_positions) >= MAX_TRADES_PER_DAY:
                    break

                symbol = pick["symbol"]
                score = pick.get("score", 0)

                # Enforce score filter
                if score < MIN_ENTRY_SCORE:
                    logger.info(f"🚫 Skipping {symbol} — score {score} < minimum {MIN_ENTRY_SCORE}")
                    continue
                if symbol in open_positions:
                    continue

                # Fetch latest prices for entry
                df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
                if df is None or len(df) < 2:
                    continue
                df = df[df.index <= current_date]
                if len(df) < 2:
                    continue

                entry_date = df.index[-2]  # Use T-1 close as entry
                entry_price = df.iloc[-2]["close"]
                qty = int(TARGET_PER_TRADE // entry_price)
                if qty == 0:
                    continue

                invested = qty * entry_price
                if invested > capital:
                    logger.warning(f"⛔ Not enough capital to buy {symbol} | Required: ₹{invested:.2f}, Available: ₹{capital:.2f}")
                    continue

                # Execute entry
                capital -= invested
                open_positions[symbol] = {
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "qty": qty
                }
                logger.info(f"🛒 Buying {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Entry Score: {score}")
                recorder.record_entry(symbol, entry_date.strftime("%Y-%m-%d"), entry_price, invested)

        # Move to next day
        current_date += timedelta(days=1)
        current_date = current_date.replace(hour=9, minute=30, second=0)

    # Export all trades
    recorder.export_csv()
    logger.info("✅ Backtest finished. Final capital: ₹{:.2f}".format(capital))

# Start backtest
if __name__ == "__main__":
    run_backtest()
