import csv
from pathlib import Path

class TradeRecorder:
    def __init__(self):
        root_dir = Path(__file__).resolve().parents[2]  # points to short-trade-assistant/
        self.output_path = root_dir / "backend" / "backtesting" / "logs" / "trades.csv"
        self.trades = []

        # Ensure the directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def record_entry(self, symbol, date, price, investment):
        self.trades.append({
            "symbol": symbol,
            "entry_date": date,
            "entry_price": price,
            "investment": investment,
            "status": "open"
        })

    def record_exit(self, symbol, date, exit_price):
        for trade in self.trades:
            if trade["symbol"] == symbol and trade["status"] == "open":
                trade["exit_date"] = date
                trade["exit_price"] = exit_price
                trade["status"] = "closed"
                trade["pnl"] = (exit_price - trade["entry_price"]) * (trade["investment"] // trade["entry_price"])

    def export_csv(self):
        if not self.trades:
            print("⚠️ No trades recorded — skipping CSV export.")
            return

        with open(self.output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
            writer.writeheader()
            writer.writerows(self.trades)
