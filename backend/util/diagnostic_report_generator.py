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
        # Swing/backtest summary (legacy)
        self.trades = []
        # Intraday (legacy single-row list for backward-compat display)
        self.intraday_diagnostics = []
        # NEW: richer intraday stores
        self.intraday_entries = {}            # trade_id -> entry diagnostics dict
        self.intraday_exit_events = []        # list of per-exit events dicts
        
    def reset_intraday(self):
        self.intraday_entries.clear()
        self.intraday_exit_events.clear()
        self.intraday_diagnostics.clear()

    
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
        # keep original behavior but also maintain keyed store
        diagnostics = dict(diagnostics)
        diagnostics["trade_id"] = trade_id
        # keyed for joins
        self.intraday_entries[trade_id] = diagnostics
        # legacy list (some notebooks may read this)
        self.intraday_diagnostics.append(diagnostics)

    def record_intraday_exit_diagnostics(self, trade_id, exit_price, pnl, exit_time, reason, qty_hint=None):
        # append per-exit event (supports multiple exits per trade)
        ev = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "exit_time": exit_time,
            "reason": reason,
        }
        if qty_hint is not None:
            ev["qty_hint"] = qty_hint
        self.intraday_exit_events.append(ev)

        # also update latest matching legacy row (for quick looks)
        for row in reversed(self.intraday_diagnostics):
            if row.get("trade_id") == trade_id:
                row.update({
                    "exit_price": exit_price,
                    "exit_time": exit_time,
                    "pnl": pnl,
                    "exit_reason": reason,
                })
                break

    def export(self, output_path):
        df = pd.DataFrame(self.trades)
        df.to_csv(output_path, index=False)
        print(f"✅ Diagnostics exported to: {output_path}")
        
    def export_intraday_diagnostics(self, path: str):
        """Legacy exporter: dumps the list of entry rows (last-exit stamped)."""
        if not self.intraday_diagnostics:
            print("⚠️ No intraday diagnostics recorded — skipping export.")
            return
        pd.DataFrame(self.intraday_diagnostics).to_csv(path, index=False)

    def export_intraday_csv(self, out_dir: str = "backtesting/diagnostics", run_id: str | None = None):
        os.makedirs(out_dir, exist_ok=True)

        # 1) Events (ensure stable columns, even when empty)
        events_df = pd.DataFrame(self.intraday_exit_events)
        event_cols = ["trade_id","exit_price","pnl","exit_time","reason","qty_hint"]
        if events_df.empty:
            events_df = pd.DataFrame(columns=event_cols)
        else:
            for c in event_cols:
                if c not in events_df.columns:
                    events_df[c] = None
            events_df = events_df[event_cols]
            events_df = events_df.sort_values(["trade_id","exit_time"])

        # 2) Entries
        entries_df = pd.DataFrame(list(self.intraday_entries.values()))
        if not entries_df.empty and "entry_time" in entries_df.columns:
            entries_df["entry_time"] = entries_df["entry_time"].astype(str)

        # 3) Final & partial joins (robust when no events)
        final_reasons = {"STOP","T1_FULL","T2","EOD"}
        final_cols   = ["trade_id","final_reason","final_exit_time","final_exit_price","final_pnl"]
        if events_df.empty:
            final_df = pd.DataFrame(columns=final_cols)
        else:
            final_df = (events_df[events_df["reason"].isin(final_reasons)]
                        .sort_values(["trade_id","exit_time"])
                        .drop_duplicates("trade_id", keep="last")
                        .rename(columns={
                            "reason":"final_reason",
                            "exit_time":"final_exit_time",
                            "exit_price":"final_exit_price",
                            "pnl":"final_pnl",
                        }))[final_cols]

        partial_cols = ["trade_id","t1_partial_time","t1_partial_price","t1_partial_pnl"]
        if events_df.empty:
            partial_df = pd.DataFrame(columns=partial_cols)
        else:
            partial_df = (events_df[events_df["reason"]=="T1_PARTIAL"]
                        .sort_values(["trade_id","exit_time"])
                        .drop_duplicates("trade_id", keep="first")
                        .rename(columns={
                            "exit_time":"t1_partial_time",
                            "exit_price":"t1_partial_price",
                            "pnl":"t1_partial_pnl",
                        }))[partial_cols]

        # 4) Build summary (writes even if entries empty)
        summary = entries_df.merge(final_df, on="trade_id", how="left")
        if not partial_df.empty:
            summary = summary.merge(partial_df, on="trade_id", how="left")

        summary_path = os.path.join(out_dir, f"diagnostic_report_intraday{f'_{run_id}' if run_id else ''}.csv")
        summary.to_csv(summary_path, index=False)
        print(f"✅ Exported intraday diagnostics → Summary: {summary_path}  Events: {events_path}")



if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python diagnostic_report_generator.py <output_folder>")
        sys.exit(1)

    output_dir = sys.argv[1]
    os.makedirs(output_dir, exist_ok=True)
    sample_output_path = os.path.join(output_dir, "diagnostic_output.csv")
