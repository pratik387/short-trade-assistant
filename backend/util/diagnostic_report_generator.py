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

# Exposed singleton proxy (thread-local)
diagnostics_tracker = _DiagnosticsProxy()


class DiagnosticsTracker:
    def __init__(self):
        # Swing/backtest summary (legacy)
        self.trades = []

        # Intraday new API
        self.intraday_entries = {}     # trade_id -> dict
        self.intraday_exit_events = [] # list[dict]
    def record_entry(self, symbol, entry_time, entry_price, score,
                     filters=None, indicators=None):
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

    def record_exit(self, symbol, exit_time, exit_price, pnl, pnl_percent, reason,
                    exit_filters=None, indicators=None, days_held=0, score_before=None,
                    score_after=None, entry_score_drop=None, entry_score_drop_pct=None):
        for trade in reversed(self.trades):
            if trade["symbol"] == symbol and trade["exit_time"] is None:
                trade.update({
                    "exit_time": exit_time,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_percent": ((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100,
                    "exit_reason": reason,
                    "exit_filters": exit_filters or [],
                    "exit_indicators": indicators or {},
                    "entry_score_before": score_before,
                    "entry_score_at_exit": score_after,
                    "entry_score_drop": entry_score_drop,
                    "entry_score_drop_pct": entry_score_drop_pct,
                    "days_held": days_held,
                    "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "neutral")
                })
                return

    # ----------------------- Intraday new API -----------------------
    def reset_intraday(self):
        self.intraday_entries.clear()
        self.intraday_exit_events.clear()

    def record_intraday_entry_diagnostics(self, trade_id: str, diagnostics: dict):
        row = dict(diagnostics or {})
        row["trade_id"] = trade_id
        self.intraday_entries[trade_id] = row

    def record_intraday_exit_diagnostics(self, trade_id: str, exit_price: float, pnl: float,
                                         exit_time: str, reason: str,
                                         exit_qty: int | None = None,
                                         pnl_actual: float | None = None,
                                         pnl_pct: float | None = None):
        ev = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "exit_time": exit_time,
            "reason": reason,
            "exit_qty": exit_qty,
            "pnl_actual": pnl_actual,
            "pnl_pct": pnl_pct,
        }
        self.intraday_exit_events.append(ev)

        row = self.intraday_entries.get(trade_id, {"trade_id": trade_id})
        row.update({
            "exit_time": exit_time,
            "exit_reason": reason,
            "exit_price": exit_price,
            "exit_qty": exit_qty,
            "pnl_per_share": pnl,
            "pnl_actual": pnl_actual,
            "pnl_pct": pnl_pct,
        })
        self.intraday_entries[trade_id] = row

    # ----------------------- Exporters -----------------------
    def export(self, output_path):
        df = pd.DataFrame(self.trades)
        df.to_csv(output_path, index=False)
        print(f"✅ Diagnostics exported to: {output_path}")

    def export_intraday_csv(self, out_dir: str = "backtesting/diagnostics", run_id: str | None = None):
        os.makedirs(out_dir, exist_ok=True)

        # ---- Events table
        events_df = pd.DataFrame(self.intraday_exit_events)
        event_cols = [
            "trade_id", "exit_time", "reason",
            "exit_price", "exit_qty",
            "pnl", "pnl_actual", "pnl_pct",
        ]
        if events_df.empty:
            events_df = pd.DataFrame(columns=event_cols)
        else:
            for c in event_cols:
                if c not in events_df.columns:
                    events_df[c] = None
            events_df = events_df[event_cols].sort_values(["trade_id", "exit_time"])

        # ---- Entries
        entries_df = pd.DataFrame(list(self.intraday_entries.values()))
        if not entries_df.empty and "entry_time" in entries_df.columns:
            entries_df["entry_time"] = entries_df["entry_time"].astype(str)
        summary = entries_df.copy()
        # First T1 partial (optional) — keep if you like it
        if not events_df.empty:
            p1 = events_df[events_df["reason"] == "T1_PARTIAL"]
            if not p1.empty:
                partial_df = (
                    p1.sort_values(["trade_id", "exit_time"])
                    .drop_duplicates("trade_id", keep="first")
                    .rename(columns={
                        "exit_time": "t1_partial_time",
                        "exit_price": "t1_partial_price",
                        "exit_qty": "t1_partial_qty",
                        "pnl": "t1_partial_pnl_per_share",
                        "pnl_actual": "t1_partial_pnl_actual",
                        "pnl_pct": "t1_partial_pnl_pct",
                    })
                )[["trade_id","t1_partial_time","t1_partial_price","t1_partial_qty",
                "t1_partial_pnl_per_share","t1_partial_pnl_actual","t1_partial_pnl_pct"]]
                summary = summary.merge(partial_df, on="trade_id", how="left")

        summary_path = os.path.join(out_dir, f"diagnostic_report_intraday{f'_{run_id}' if run_id else ''}.csv")
        summary.to_csv(summary_path, index=False)
        return summary_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python diagnostic_report_generator.py <output_folder>")
        sys.exit(1)

    output_dir = sys.argv[1]
    os.makedirs(output_dir, exist_ok=True)
    sample_output_path = os.path.join(output_dir, "diagnostic_output.csv")
