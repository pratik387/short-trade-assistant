from tinydb import TinyDB
from collections import defaultdict

MOCK_TRADES_PATH = "backend/mock_trades.json"
MOCK_PNL_PATH = "backend/mock_pnl.json"

def analyze_and_store_pnl():
    db_trades = TinyDB(MOCK_TRADES_PATH)
    db_pnl = TinyDB(MOCK_PNL_PATH)
    db_pnl.truncate()

    all_trades = db_trades.all()
    summary = defaultdict(lambda: {"buy": [], "sell": []})

    for trade in all_trades:
        summary[trade["symbol"]][trade["action"].lower()].append(trade)

    for symbol, data in summary.items():
        buys, sells = data["buy"], data["sell"]
        if not buys or not sells:
            continue

        total_buy_qty = sum(t["quantity"] for t in buys)
        total_sell_qty = sum(t["quantity"] for t in sells)
        matched_qty = min(total_buy_qty, total_sell_qty)

        avg_buy = sum(t["price"] * t["quantity"] for t in buys) / total_buy_qty
        avg_sell = sum(t["price"] * t["quantity"] for t in sells) / total_sell_qty
        pnl = (avg_sell - avg_buy) * matched_qty

        db_pnl.insert({
            "symbol": symbol,
            "avg_buy_price": round(avg_buy, 2),
            "avg_sell_price": round(avg_sell, 2),
            "quantity_matched": matched_qty,
            "pnl": round(pnl, 2)
        })

if __name__ == "__main__":
    analyze_and_store_pnl()
