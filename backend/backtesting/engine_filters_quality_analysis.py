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
from backtesting.backtest_config import BACKTEST_CONFIG
from config.filters_setup import load_filters
from db.tinydb.client import get_table
from util.util import is_market_active
from config.logging_config import get_loggers, switch_agent_log_file
from backtesting.config_tracker import get_combined_config_hash
import subprocess
from pathlib import Path

HASH_PATH = Path(".score_cache/global_config.hash")

# Trading parameters
PROFIT_TARGET = BACKTEST_CONFIG["profit_target"]
STOP_LOSS_THRESHOLD = BACKTEST_CONFIG["stop_loss_threshold"]
MIN_ENTRY_SCORE = BACKTEST_CONFIG["minimum_entry_score"]
MAX_HOLD_DAYS = BACKTEST_CONFIG["maximum_holding_days"]

logger, trade_logger = get_loggers()

def ensure_fresh_score_cache():
    current_hash = get_combined_config_hash()
    if HASH_PATH.exists() and HASH_PATH.read_text().strip() == current_hash:
        print("✅ Config unchanged. Using cached scores.")
        return
    print("⚠️ Config changed. Running ohlcv_data_downloader.py to refresh scores...")
    subprocess.run([sys.executable, "backend/backtesting/ohlcv_data_downloader.py"])

    HASH_PATH.write_text(current_hash)

def run_quality_analysis():
    config = load_filters()
    broker = MockBroker(use_cache=True)
    broker.get_ltp = lambda symbol: {symbol: broker.fetch_candles(symbol, interval="day").iloc[-1]["close"]}

    entry_service = EntryService(broker, config, "all", "swing")
    portfolio_db = get_table("portfolio")
    exit_service = ExitService(config=config, portfolio_db=portfolio_db, data_provider=broker)
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
            logger.info(f"🜕️ Processing {current_date.strftime('%Y-%m-%d')} | Open Positions: {len(open_positions)}")

            if not is_market_active(current_date):
                current_date += timedelta(days=1)
                continue

            # Exit logic for current holdings
            for symbol in list(open_positions.keys()):
                position = open_positions[symbol]
                lookback_days = config.get("exit_lookback_days", 30)
                from_date = current_date - timedelta(days=lookback_days)
                df = broker.fetch_candles(symbol, interval="day", from_date=from_date, to_date=current_date)
                if df is None or len(df) < 2:
                    continue
                df = df[df.index <= current_date]
                if len(df) < 2:
                    continue
                buy_date = position["entry_date"]
                days_held = (current_date - buy_date).days
                position["final_score"] = df.iloc[-1].get("score", 0)

                result = exit_service.evaluate_exit_decision(position, current_date=current_date, df=df)
                if result["recommendation"] in ["EXIT", "REDUCE"]:
                    qty = position["qty"]
                    exit_price = result["current_price"]
                    pnl = qty * (exit_price - position["entry_price"])
                    capital += qty * exit_price

                    logger.info(f"✅ Exiting {symbol} at ₹{exit_price:.2f} | PnL: ₹{pnl:.2f} | Reason: {result['exit_reason']}")
                    exit_service.execute_exit(position, result, current_date)
                    recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                    del open_positions[symbol]

                elif days_held >= MAX_HOLD_DAYS:
                    logger.info(f"⏳ Forced exit for {symbol}: held {days_held} days ≥ max {MAX_HOLD_DAYS}")
                    exit_price = df["close"].iloc[-1]
                    entry_price = position["entry_price"]
                    qty = position["qty"]
                    pnl = qty * (exit_price - entry_price)
                    days_held = (current_date - position["entry_date"]).days

                    raw_reasons = [{"filter": "forced_max_hold", "weight": 0, "reason": "Held beyond max days"}]

                    result = {
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "current_price": exit_price,
                        "pnl": round(pnl, 2),
                        "pnl_percent": round(((exit_price - entry_price) / entry_price) * 100, 2),
                        "days_held": days_held,
                        "recommendation": "EXIT",
                        "exit_reason": "forced_max_hold",
                        "score": position.get("score", 0),
                        "reasons": raw_reasons,
                        "breakdown": [(r["filter"], r["weight"], r["reason"]) for r in raw_reasons]
                    }
                    exit_service.execute_exit(position, result, current_date)
                    capital += position["qty"] * df["close"].iloc[-1]
                    recorder.record_exit(symbol, current_date.strftime("%Y-%m-%d"), exit_price)
                    del open_positions[symbol]
                    continue

            # Entry logic with no limits — buy 1 share only
            suggestions = entry_service.get_suggestions(as_of_date=current_date)
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
                    "entry_date": current_date,
                    "entry_price": entry_price,
                    "qty": qty,
                    "score": score,
                    "symbol": symbol,
                    "entry_filters": pick.get("reasons", []),       # optional
                    "entry_indicators": pick.get("indicators", {})  # optional
                }

                entry_service.execute_entry(pick, quantity=qty, timestamp=current_date, entry_price=entry_price)
                logger.info(f"📂 Buying {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Entry Score: {score}")
                trade_logger.info(f"ENTRY | {symbol} | Qty: {qty} | Entry Price: ₹{entry_price:.2f} | Invested: ₹{invested:.2f} | Score: {score}")
                recorder.record_entry(symbol, entry_date.strftime("%Y-%m-%d"), entry_price, invested)

            current_date += timedelta(days=1)
            current_date = current_date.replace(hour=9, minute=30, second=0)

        # Final exits
        for symbol, pos in list(open_positions.items()):
            df = broker.fetch_candles(symbol, interval="day", from_date=start_date, to_date=end_date)
            df = df[df.index <= current_date]
            result = exit_service._build_exit_result(
                df=df,
                stock=pos,
                current_date=current_date,
                reason="Forced exit at end"
            )
            result["reasons"] = [{"filter": "forced_exit", "weight": 0, "reason": "Forced exit at end"}]
            result["breakdown"] = [("forced_exit", 0, "Forced exit at end")]

            exit_service.execute_exit(pos, result, current_date)
            capital += pos["qty"] * result["current_price"]
            pnl = pos["qty"] * (result["current_price"] - pos["entry_price"])
            logger.info(f"📄 Force Exit {symbol} | Qty: {pos['qty']} | Exit: ₹{result['current_price']:.2f} | PnL: ₹{pnl:.2f}")
            recorder.record_exit(symbol, end_date.strftime("%Y-%m-%d"), result["current_price"])
            del open_positions[symbol]

        recorder.export_csv()
        logger.info("✅ Backtest finished. Final capital: ₹{:.2f}".format(capital))

    except Exception as e:
        logger.exception(f"Failed: {e}")

if __name__ == "__main__":
    ensure_fresh_score_cache()
    print("🚀 Now running run_quality_analysis()")
    from engine_filters_quality_analysis import run_quality_analysis
    run_quality_analysis()
