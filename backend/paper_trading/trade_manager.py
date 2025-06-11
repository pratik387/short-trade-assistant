import pandas as pd
from pathlib import Path
import json
from paper_trading.capital_tracker import get_available_capital, update_capital
from paper_trading.portfolio import add_mock_stock, get_open_positions, mark_stock_sold
from paper_trading.logger import log_event
from services.suggestion_logic import get_filtered_stock_suggestions
from services.exit_service import ExitService
from brokers.kite.kite_exit_data_provider import KiteExitDataProvider
from db.tinydb.client import get_table
from services.notification.email_alert import send_exit_email
from jobs.refresh_holidays import download_nse_holidays

TARGET_PER_TRADE = 20000
MAX_TRADES_PER_SESSION = 5
HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "assets" / "nse_holidays.csv"


def run_paper_trading_cycle():
    try:
        if not is_market_active():
            log_event("📅 Market inactive — skipping trading cycle.")
            return

        capital = get_available_capital()
        if capital < TARGET_PER_TRADE:
            log_event(f"💸 Insufficient capital (₹{capital}) for new trades. Skipping.")
            return

        suggestions = get_filtered_stock_suggestions(index="all")
        trades_made = 0

        for stock in suggestions:
            if trades_made >= MAX_TRADES_PER_SESSION or capital < TARGET_PER_TRADE:
                break

            price = stock["close"]
            qty = int(TARGET_PER_TRADE / price)
            amount = qty * price

            success = add_mock_stock(stock["symbol"], price, qty)
            if success:
                update_capital(-amount)
                capital -= amount
                log_event(f"🟢 Bought {stock['symbol']} @ ₹{price} x {qty} = ₹{amount:.2f}")
                trades_made += 1
            else:
                log_event(f"⚠️ {stock['symbol']} already tracked. Skipping.")

        if trades_made == 0:
            log_event("📭 No new trades executed this cycle.")

    except Exception as e:
        log_event(f"❌ Error during paper trading cycle: {e}")


def check_exit_conditions():
    try:
        if not is_market_active():
            log_event("📅 Market inactive — skipping exit check.")
            return

        data_provider = KiteExitDataProvider(interval="day")
        portfolio_db = get_table("portfolio")
        service = ExitService(
            config=data_provider.config,
            portfolio_db=portfolio_db,
            data_provider=data_provider,
            notifier=send_exit_email,
            blocked_logger=log_event
        )

        open_stocks = get_open_positions()
        if not open_stocks:
            log_event("📁 No open positions to evaluate for exit.")
            return

        for stock in open_stocks:
            try:
                df = data_provider.fetch_exit_data(stock)
                if df is None or df.empty:
                    log_event(f"⚠️ No data for {stock['symbol']}, skipping.")
                    continue

                current_price = df["close"].iloc[-1]
                actions = service._evaluate_exit(stock, current_price, df)
                for action in actions:
                    qty = action["qty"]
                    reason = action["reason"]
                    pnl = (current_price - stock["buy_price"]) * qty
                    update_capital(current_price * qty)
                    mark_stock_sold(stock["symbol"])
                    log_event(
                        f"🔴 Sold {stock['symbol']} @ ₹{current_price:.2f} | Qty: {qty} | "
                        f"Reason: {reason} | P&L: ₹{pnl:.2f}"
                    )
            except Exception as e:
                log_event(f"❌ Error during exit check for {stock['symbol']}: {e}")

    except Exception as e:
        log_event(f"❌ Error in exit check routine: {e}")


def is_market_active(date=None):
    """
    Check if the market is active for a given date/time.
    Loads holiday dates from the JSON file and applies weekend and session checks.
    Returns True if open, False if closed.
    """
    try:
        now = pd.Timestamp.now(tz="Asia/Kolkata")
        # Normalize date parameter or use today's date
        if date is None:
            check_date = now.normalize()
        else:
            check_date = pd.to_datetime(date).normalize()

        # Weekend check (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            log_event(f"⛔ {check_date.date()} is weekend; market closed.")
            return False

        # Load holiday entries
        try:
            with open(HOLIDAY_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except FileNotFoundError:
            log_event(f"⚠️ Holidays file not found at {HOLIDAY_FILE!s}. Downloading fresh copy…")
            res = download_nse_holidays()
            if res.get("status") == "success":
                with open(HOLIDAY_FILE, "r", encoding="utf-8") as f:
                    items = json.load(f)
            else:
                log_event("❌ Could not fetch holidays; assuming market is open.")
                return True

        # Parse holiday dates
        dates = []
        for item in items:
            # support both keys
            raw = item.get("tradingDate") or item.get("holidayDate")
            try:
                dt = pd.to_datetime(raw, format="%d-%b-%Y", errors="coerce").normalize()
                if not pd.isna(dt):
                    dates.append(dt)
            except Exception:
                continue

        if check_date in dates:
            log_event(f"⛔ {check_date.date()} is a market holiday.")
            return False

        # Market session hours: 9:15am – 3:30pm IST
        open_time = now.replace(hour=9, minute=15, second=0)
        close_time = now.replace(hour=15, minute=30, second=0)
        is_open = open_time <= now <= close_time
        log_event(f"Market status at {now.time()}: {'Open' if is_open else 'Closed'}")
        return is_open

    except Exception as e:
        log_event(f"⚠️ Could not determine market status: {e}")
        return False
