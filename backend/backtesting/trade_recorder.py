import csv
from config.logging_config import get_loggers, get_log_directory
from util.diagnostic_report_generator import diagnostics_tracker
logger, trade_logger = get_loggers()

class TradeRecorder:
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id
        self.log_folder_path = get_log_directory()
        self.output_path = self.log_folder_path / "trades.csv"
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

        prefix = f"intraday_{self.run_id}_" if self.run_id else ""
        output_csv_path = str(self.log_folder_path / f"{prefix}diagnostic_report.csv")
        diagnostics_tracker.export(output_csv_path)
        output_intraday_csv_path = str(self.log_folder_path / f"{prefix}diagnostic_report_intraday.csv")
        diagnostics_tracker.export_intraday_diagnostics(output_intraday_csv_path)

        logger.info(f"📊 Diagnostics report saved to: {output_csv_path}")
        logger.info(f"📊 Intraday Diagnostics report saved to: {output_intraday_csv_path}")
