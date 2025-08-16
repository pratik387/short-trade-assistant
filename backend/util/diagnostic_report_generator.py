import os
import sys
import pandas as pd

import threading
_tls = threading.local()

def _get_tracker():
    if not hasattr(_tls, "inst"):
        _tls.inst = DiagnosticsTracker()
    return _tls.inst

class _DiagnosticsProxy:
    def __getattr__(self, name):
        return getattr(_get_tracker(), name)

# replace: diagnostics_tracker = DiagnosticsTracker()
diagnostics_tracker = _DiagnosticsProxy()

class DiagnosticsTracker:
    def __init__(self):
        self.trades = []
        self.intraday_diagnostics = []

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
            "pnl_percent": None,
            "exit_reason": None,
            "exit_filters": [],
            "exit_indicators": {},
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
            
    def record_intraday_entry_diagnostics(self, trade_id: str, diagnostics: dict):
            diagnostics["trade_id"] = trade_id
            self.intraday_diagnostics.append(diagnostics)
        
    def record_intraday_exit_diagnostics(self, trade_id, exit_price, pnl, exit_time, reason):
        for row in self.intraday_diagnostics:
            if row.get("trade_id") == trade_id:
                row["exit_price"] = exit_price
                row["exit_time"] = exit_time
                row["pnl"] = pnl
                row["exit_reason"] = reason
                return

    def export(self, output_path):
        df = pd.DataFrame(self.trades)
        df.to_csv(output_path, index=False)
        print(f"✅ Diagnostics exported to: {output_path}")
        
    def export_intraday_diagnostics(self, path: str):
        if not self.intraday_diagnostics:
            print("⚠️ No intraday diagnostics recorded — skipping export.")
            return

        df = pd.DataFrame(self.intraday_diagnostics)
        df.to_csv(path, index=False)



if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python diagnostic_report_generator.py <output_folder>")
        sys.exit(1)

    output_dir = sys.argv[1]
    os.makedirs(output_dir, exist_ok=True)
    sample_output_path = os.path.join(output_dir, "diagnostic_output.csv")

diagnostics_tracker = _DiagnosticsProxy()
