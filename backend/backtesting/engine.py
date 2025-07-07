import sys
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Imports
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services.entry_service import EntryService
from services.exit_service import ExitService
from brokers.mock.mock_broker import MockBroker
from backtesting.trade_recorder import TradeRecorder
from backtesting.config import BACKTEST_CONFIG
from config.filters_setup import load_filters
from db.tinydb.client import get_table
from util.util import is_market_active
from config.logging_config import get_loggers, switch_agent_log_file

# Trading parameters
TARGET_PER_TRADE = BACKTEST_CONFIG["capital_per_trade"]
MAX_TRADES_PER_DAY = BACKTEST_CONFIG["max_trades_per_day"]
MAX_HOLD_DAYS = BACKTEST_CONFIG["max_hold_days"]
PROFIT_TARGET = BACKTEST_CONFIG["profit_target"]
STOP_LOSS_THRESHOLD = BACKTEST_CONFIG["stop_loss_threshold"]
MIN_ENTRY_SCORE = BACKTEST_CONFIG["minimum_entry_score"]
MIN_HOLD_DAYS = BACKTEST_CONFIG["minimum_holding_days"]
MIN_SCORE_GAP_TO_REPLACE = BACKTEST_CONFIG.get("min_score_gap_to_replace")

logger, trade_logger = get_loggers()

def place_order_entry(broker, symbol, qty, entry_price, entry_date, score):
    broker.place_order(symbol=symbol, quantity=qty, action="buy", timestamp = entry_date)
    invested = qty * entry_price
    logger.info(f"🛂 Buying {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Entry Score: {score}")
    trade_logger.info(f"ENTRY | {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Score: {score}")
    return invested

def place_order_exit(broker, symbol, qty, exit_price, entry_price, reason, exit_date):
    broker.place_order(symbol=symbol, quantity=qty, action="sell", timestamp = exit_date)
    pnl = qty * (exit_price - entry_price)
    logger.info(f"✅ Exiting {symbol} at ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} | Reason: {reason}")
    trade_logger.info(f"EXIT | {symbol} | Qty: {qty} | Entry: ₹{entry_price:.2f} | Exit: ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} {reason}")
    return pnl

def run_backtest():
    config = load_filters()
    broker = MockBroker(use_cache=True)
    entry_service = EntryService(broker, config, "nifty_500")
    portfolio_db = get_table("portfolio")
    exit_service = ExitService(config=config, portfolio_db=portfolio_db, data_provider=broker)
    recorder = TradeRecorder()

    capital = BACKTEST_CONFIG["capital"]
    open_positions = {}

    start_date = datetime.strptime(BACKTEST_CONFIG["start_date"], "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    end_date = datetime.strptime(BACKTEST_CONFIG["end_date"], "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    current_date = start_date.replace(hour=9, minute=30, second=0)
    last_logged_month = None
    try:
        while current_date <= end_date:
            month_str = current_date.strftime("%Y-%m")
            if month_str != last_logged_month:
                switch_agent_log_file(month_str)
                last_logged_month = month_str

            logger.info(f"📅 Processing {current_date.strftime('%Y-%m-%d')} | Available capital: ₹{capital:.2f}")
            if capital < 0:
                logger.warning(f"⚠️ Capital dropped below zero: ₹{capital:.2f}")

            current_check_time = current_date.replace(hour=9, minute=30)
            if not is_market_active(current_check_time):
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
                entry_score = position["score"]
                current_close = df.iloc[-1]["close"]
                day_low = df.iloc[-1]["low"]
                stop_loss_price = entry_price * (1 + STOP_LOSS_THRESHOLD / 100)
                days_held = (current_date - buy_date).days

                if days_held < MIN_HOLD_DAYS:
                    logger.info(f"⏳ Skipping exit for {symbol}: held {days_held} days < min {MIN_HOLD_DAYS}")
                    continue

                result = exit_service.evaluate_exit_filters(symbol, entry_price, buy_date, current_date=current_date, entry_score=entry_score)
                allow_exit = result["recommendation"] == "EXIT"
                exit_score = result.get("final_score")
                score_before = position.get("score", "?")
                score_log = f"Score {score_before} → {exit_score}" if score_before != "?" else f"Final Exit Score: {exit_score}"

                trigger_exit = False
                reason = "exit signal"
                exit_price = current_close

                if (day_low <= stop_loss_price and days_held == 0):
                    reason = f"🔝 stop-loss hit intraday (low: ₹{day_low:.2f} <= SL ₹{stop_loss_price:.2f})"
                    exit_price = stop_loss_price
                    trigger_exit = True
                elif (day_low <= stop_loss_price and days_held != 0):
                    reason = f"🔝 stop-loss hit (low: ₹{day_low:.2f} <= SL ₹{stop_loss_price:.2f})"
                    exit_price = stop_loss_price
                    trigger_exit = True
                elif ((current_close - entry_price) / entry_price) * 100 >= PROFIT_TARGET:
                    reason = f"💰 profit target hit ({((current_close - entry_price) / entry_price) * 100:.2f}%)"
                    trigger_exit = True
                elif allow_exit:
                    reasons = result.get("reasons", [])
                    reason_lines = [f"🔁 exit filters triggered | {score_log}"]
                    for r in reasons:
                        filter_name = r.get("filter")
                        note = r.get("reason")
                        weight = r.get("weight", "")
                        line = f"  • {filter_name} (-{weight}): {note}" if weight != "" else f"  • {filter_name}: {note}"
                        reason_lines.append(line)
                    reason = "".join(reason_lines)
                    trigger_exit = True
                elif days_held >= MAX_HOLD_DAYS:
                    reason = f"⏳ max hold days reached ({days_held}d)"
                    trigger_exit = True

                if trigger_exit:
                    qty = position["qty"]
                    pnl = place_order_exit(broker, symbol, qty, exit_price, entry_price, reason, current_date)
                    capital += qty * exit_price
                    recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                    del open_positions[symbol]

            suggestions = entry_service.get_suggestions()
            top_picks = sorted([s for s in suggestions if s.get("score", 0) >= MIN_ENTRY_SCORE], key=lambda x: x.get("score", 0), reverse=True)

            for pick in top_picks:
                symbol = pick["symbol"]
                score = pick.get("score", 0)

                if symbol in open_positions:
                    continue

                # Rebalancing logic
                weakest_symbol = None
                weakest_score = float("inf")
                for held_symbol, pos in open_positions.items():
                    held_score = pos.get("score", 0)
                    if held_score < weakest_score:
                        weakest_score = held_score
                        weakest_symbol = held_symbol

                if weakest_symbol is not None and weakest_score is not None and score is not None and (score - weakest_score) >= MIN_SCORE_GAP_TO_REPLACE:
                    logger.info(f"🔁 Rebalancing: Replacing {weakest_symbol} (Score: {weakest_score}) with {symbol} (Score: {score})")
                    weak_pos = open_positions[weakest_symbol]
                    qty = weak_pos["qty"]
                    exit_price = broker.get_ltp(weakest_symbol)
                    pnl = place_order_exit(broker, weakest_symbol, qty, exit_price, weak_pos["entry_price"], "🔁 Rebalanced for better candidate", current_date)
                    capital += qty * exit_price
                    recorder.record_exit(weakest_symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                    del open_positions[weakest_symbol]

                elif len(open_positions) >= MAX_TRADES_PER_DAY:
                    continue

                df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
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

                invested = place_order_entry(broker, symbol, qty, entry_price, current_date, score)
                capital -= invested
                open_positions[symbol] = {
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "qty": qty,
                    "score": score
                }
                recorder.record_entry(symbol, entry_date.strftime("%Y-%m-%d"), entry_price, invested)

            current_date += timedelta(days=1)
            current_date = current_date.replace(hour=9, minute=30, second=0)

        for symbol, pos in open_positions.items():
            exit_price = broker.get_ltp(symbol)
            pnl = place_order_exit(broker, symbol, pos["qty"], exit_price, pos["entry_price"], "📄 Forced exit at end", end_date)
            capital += pos["qty"] * exit_price
            recorder.record_exit(symbol, end_date.strftime("%Y-%m-%d"), exit_price)

        recorder.export_csv()
        logger.info("✅ Backtest finished. Final capital: ₹{:.2f}".format(capital))

    except Exception as e:
        logger.exception(f"Failed: {e}")

if __name__ == "__main__":
    run_backtest()
