import sys
import json
from pathlib import Path
# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.entry_service import evaluate_symbol
from config.filters_setup import load_filters

# CONFIG
ARCHIVE_DIR = Path("backend/backtesting/ohlcv_archive")
OUTPUT_FOLDER = Path("backend/cache/suggestions/mock")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

START_DATE = "2023-01-01"
END_DATE = "2025-06-01"
LOOKBACK_DAYS = 180
MAX_WORKERS = 16
DAY_PARALLELISM = 4
TOP_N = 100
MIN_SCORE = 1.0

config = load_filters()

# Load all symbols from the NSE JSON index file
INDEX_FILE = Path(__file__).resolve().parents[1] / "assets" / "indexes" / "nse_all.json"
with open(INDEX_FILE) as f:
    data = json.load(f)
    ALL_SYMBOLS = [entry["symbol"] for entry in data]

def tie_breaker(x):
    return (
        -x.get("score", 0),
        -x.get("adx", 0),
        abs(x.get("rsi", 50) - 50),
        -x.get("volume", 0),
    )

def load_df(symbol: str):
    folder = ARCHIVE_DIR / symbol
    if not folder.exists():
        return None
    files = list(folder.glob(f"{symbol}_1d_*.feather"))
    if not files:
        return None
    df = pd.read_feather(files[-1])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df.set_index("date", inplace=True)
    return df

def get_suggestion(symbol, current_date):
    df = load_df(symbol)
    if df is None or len(df) < LOOKBACK_DAYS:
        return None
    df = df[df.index <= current_date]
    if len(df) < LOOKBACK_DAYS:
        return None
    candle_cache = {symbol: df}
    result = evaluate_symbol({"symbol": symbol}, config, candle_cache, current_date)
    if result and result.get("score", 0) >= MIN_SCORE:
        return result
    return None

def generate_for_day(current):
    date_str = current.strftime("%Y-%m-%d")
    output_path = OUTPUT_FOLDER / f"suggestions_all_{date_str}.json"
    if output_path.exists():
        print(f"✅ {output_path.name} already exists")
        return

    print(f"🟡 Generating suggestions for {date_str}...")
    suggestions = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(get_suggestion, symbol, current): symbol for symbol in ALL_SYMBOLS}
        for future in as_completed(futures):
            result = future.result()
            if result:
                suggestions.append(result)

    # Sort with tie-breaker and take top N
    suggestions = sorted(suggestions, key=tie_breaker)[:TOP_N]

    with open(output_path, "w") as f:
        json.dump(suggestions, f, indent=2)
    print(f"💾 Saved {len(suggestions)} suggestions → {output_path.name}")

# MAIN
date_list = []
current = datetime.strptime(START_DATE, "%Y-%m-%d")
end = datetime.strptime(END_DATE, "%Y-%m-%d")
while current <= end:
    date_list.append(current)
    current += timedelta(days=1)

with ThreadPoolExecutor(max_workers=DAY_PARALLELISM) as day_executor:
    day_executor.map(generate_for_day, date_list)
