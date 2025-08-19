from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys, os, glob
from pathlib import Path
import pandas as pd
# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.intraday_engine import IntradayBacktestEngine, EngineConfig
from config.logging_config import get_loggers
from util.diagnostic_report_generator import DiagnosticsTracker

logger, _ = get_loggers()

def run_single_day(date: datetime) -> dict:
    try:
        logger.info(f"🚀 Starting backtest for {date.date()}")
        engine = IntradayBacktestEngine(EngineConfig(test_date=date))
        result = engine.run()
        logger.info(f"✅ Finished {date.date()} — {result}")
        return {"date": str(date.date()), "result": result}
    except Exception as e:
        logger.exception(f"❌ Error on {date.date()}: {e}")
        return {"date": str(date.date()), "error": str(e)}

def run_parallel_backtest(start_date_str: str, end_date_str: str, max_workers: int = 5):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    test_dates = []
    current_date = start_date
    while current_date <= end_date:
        test_dates.append(current_date)
        current_date += timedelta(days=1)

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_date = {executor.submit(run_single_day, d): d for d in test_dates}
        for future in as_completed(future_to_date):
            results.append(future.result())
            
        master_csv = _merge_and_write_diagnostics(results, start_date_str, end_date_str)
        if master_csv:
            logger.info(f"✅ Wrote single diagnostics CSV → {master_csv}")
        else:
            logger.info("ℹ️ No diagnostics to merge.")
        logger.info("📊 All backtests completed.")
        return results

# ADD anywhere in this file (e.g., below other helpers)
def _merge_and_write_diagnostics(results, start_date_str: str, end_date_str: str):
    """
    Creates ONE diagnostics CSV for the whole run.
    1) Prefer in-memory rows returned by engines (diag_entries/diag_events + log_folder).
    2) Fallback: if engines didn't return rows, merge per-day CSVs found in the log folder.
    Returns the path to the single CSV, or None if nothing to write.
    """
    combined_entries = {}
    combined_events  = []
    first_log_dir    = None

    # --- Prefer in-memory payload from engines ---
    for r in results:
        res = (r or {})
        if isinstance(res, dict) and "result" in res:
            res = res["result"]
        if not isinstance(res, dict):
            continue
        e = res.get("diag_entries") or {}
        v = res.get("diag_events") or []
        if e or v:
            combined_entries.update(e)
            combined_events.extend(v)
        if not first_log_dir and res.get("log_folder"):
            first_log_dir = res["log_folder"]

    if combined_entries or combined_events:
        tracker = DiagnosticsTracker()
        tracker.intraday_entries = combined_entries
        tracker.intraday_exit_events = combined_events
        out_dir   = first_log_dir or "logs"
        run_label = f"{start_date_str}_{end_date_str}"
        tracker.export_intraday_csv(out_dir=out_dir, run_id=run_label)
        return str(Path(out_dir) / f"diagnostic_report_intraday_{run_label}.csv")



if __name__ == "__main__":
    run_parallel_backtest("2023-01-02", "2023-03-03", max_workers=5)
