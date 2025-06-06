import json
from datetime import datetime
from pathlib import Path

# Simulated Kite object placeholder
from backend.services.kite_client import kite

MOCK_TRADES_PATH = Path(__file__).resolve().parents[1] / "mock_trades.json"

def execute_trade(symbol, quantity, action, mode="mock", price=None):
    if mode == "live":
        return execute_kite_trade(symbol, quantity, action)
    else:
        return record_mock_trade(symbol, quantity, action, price)

def execute_kite_trade(symbol, quantity, action):
    try:
        order_id = kite.place_order(
            tradingsymbol=symbol,
            exchange="NSE",
            transaction_type=action.upper(),  # "BUY" or "SELL"
            quantity=quantity,
            order_type="MARKET",
            product="MIS",
            variety="regular"
        )
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def record_mock_trade(symbol, quantity, action, price=None):
    MOCK_TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not MOCK_TRADES_PATH.exists():
            with open(MOCK_TRADES_PATH, "w") as f:
                json.dump([], f)

        with open(MOCK_TRADES_PATH, "r") as f:
            trades = json.load(f)

        mock_price = price if price else 100.0  # fallback mock price

        trades.append({
            "symbol": symbol,
            "action": action.upper(),
            "price": round(mock_price, 2),
            "quantity": quantity,
            "timestamp": datetime.now().isoformat()
        })

        with open(MOCK_TRADES_PATH, "w") as f:
            json.dump(trades, f, indent=2)

        from backend.services.mock_trade_analyzer import analyze_mock_trades

        # Log current P&L snapshot after this trade
        summary = analyze_mock_trades()
        symbol_summary = summary.get(symbol)
        if symbol_summary:
            print(f"[P&L] {symbol} | Qty: {symbol_summary['quantity_matched']} | "
                f"Buy: {symbol_summary['avg_buy_price']} | "
                f"Sell: {symbol_summary['avg_sell_price']} | "
                f"PnL: ₹{symbol_summary['pnl']}")

        return {"status": "mocked", "symbol": symbol, "action": action, "price": mock_price}

    except Exception as e:
        return {"status": "error", "message": str(e)}
