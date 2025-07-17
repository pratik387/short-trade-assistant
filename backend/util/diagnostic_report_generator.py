import os
import sys
import pandas as pd
from datetime import datetime


class DiagnosticsTracker:
    def __init__(self):
        self.trades = []

    def record_entry(self, symbol, entry_time, entry_price, score, filters=None, indicators=None):
        trade = {
            "symbol": symbol,
            "entry_date": entry_time,
            "entry_price": entry_price,
            "score": score,
            "filters": filters or [],
            "indicators": indicators or {},
            "exit_time": None,
            "exit_price": None,
            "pnl": None,
            "exit_reason": None,
            "exit_filters": [],
            "exit_indicators": {},
            "exit_score_before": None,
            "exit_score_after": None,
            "pnl_percent": None,
            "result": None
        }
        self.trades.append(trade)

    def record_exit(self, symbol, exit_time, exit_price, pnl, pnl_percent, reason, exit_filters=None, indicators=None, days_held=0, score_before=None, score_after=None, entry_score_drop=None, entry_score_drop_pct=None):
        for trade in reversed(self.trades):
            if trade["symbol"] == symbol and trade["exit_time"] is None:
                trade.update({
                    "exit_time": exit_time,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "exit_reason": reason,
                    "exit_filters": exit_filters or [],
                    "exit_indicators": indicators or {},
                    "entry_score_before": score_before,
                    "entry_score_at_exit": score_after,
                    "entry_score_drop": entry_score_drop,
                    "entry_score_drop_pct": entry_score_drop_pct,
                    "days_held": days_held,
                    "pnl_percent": ((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100,
                    "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "neutral")
                })
                return


    def export(self, output_path):
        df = pd.DataFrame(self.trades)
        df.to_csv(output_path, index=False)
        print(f"✅ Diagnostics exported to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python diagnostic_report_generator.py <output_folder>")
        sys.exit(1)

    output_dir = sys.argv[1]
    os.makedirs(output_dir, exist_ok=True)
    sample_output_path = os.path.join(output_dir, "diagnostic_output.csv")

diagnostics_tracker = DiagnosticsTracker()
