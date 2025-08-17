from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path
# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.intraday_engine import IntradayBacktestEngine, EngineConfig
from config.logging_config import get_loggers

logger, _ = get_loggers()

def run_single_day(date: datetime) -> dict:
    try:
        logger.info(f"🚀 Starting backtest for {date.date()}")
        engine = IntradayBacktestEngine(EngineConfig(test_date=date))
        result = engine.run()
        logger.info(f"✅ Finished {date.date()} — {result}")
        return {"date": str(date.date()), "result": result}
    except Exception as e:
        logger.error(f"❌ Error on {date.date()}: {e}")
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

    logger.info("📊 All backtests completed.")
    return results


if __name__ == "__main__":
    # 🔁 Example usage
    result = run_parallel_backtest("2023-01-02", "2023-03-01", max_workers=5)

    for r in result:
        print(r)
