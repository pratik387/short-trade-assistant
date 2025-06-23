# @role: Analyzes trade performance and outcome post-exit
# @used_by: project_map.py
# @filter_type: utility
# @tags: trading, analytics, post_trade
import logging
from collections import defaultdict
from db.tinydb.client import get_table

logger = logging.getLogger(__name__)

def analyze_trades():
    try:
        trades_db = get_table("trades")
        pnl_db = get_table("pnl")
        pnl_db.truncate()

        all_trades = trades_db.all()
        summary = defaultdict(lambda: {"buy": [], "sell": []})

        for trade in all_trades:
            action = trade.get("action", "").lower()
            if action in ["buy", "sell"]:
                summary[trade["symbol"]][action].append(trade)

        for symbol, grouped in summary.items():
            buys = grouped["buy"]
            sells = grouped["sell"]
            if not buys or not sells:
                continue

            total_buy_qty = sum(t["quantity"] for t in buys)
            total_sell_qty = sum(t["quantity"] for t in sells)
            matched_qty = min(total_buy_qty, total_sell_qty)

            try:
                avg_buy = sum(t["price"] * t["quantity"] for t in buys) / total_buy_qty
                avg_sell = sum(t["price"] * t["quantity"] for t in sells) / total_sell_qty
            except ZeroDivisionError:
                logger.warning(f"Division by zero for {symbol} - skipping")
                continue

            pnl = (avg_sell - avg_buy) * matched_qty

            pnl_db.insert({
                "symbol": symbol,
                "avg_buy_price": round(avg_buy, 2),
                "avg_sell_price": round(avg_sell, 2),
                "quantity_matched": matched_qty,
                "pnl": round(pnl, 2)
            })

        logger.info("✅ P&L analysis completed and stored.")

    except Exception as e:
        logger.exception("❌ Failed to analyze trades")