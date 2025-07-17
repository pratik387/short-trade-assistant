import sys
import yfinance as yf
import pandas as pd
import json
from pathlib import Path

# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.filters_setup import load_filters
from services.indicator_enrichment_service import enrich_with_indicators_and_score

# Archive directory to store historical backtest data
ARCHIVE_DIR = Path(__file__).resolve().parent / "ohlcv_archive"
ARCHIVE_DIR.mkdir(exist_ok=True)

config = load_filters()

# Load all symbols from the NSE JSON index file
INDEX_FILE = Path(__file__).resolve().parents[1] / "assets" / "indexes" / "nse_all.json"
with open(INDEX_FILE) as f:
    data = json.load(f)
    ALL_SYMBOLS = [entry["symbol"] for entry in data]

# Configurable params
START_DATE = "2022-01-01"
END_DATE = "2025-07-14"
INTERVALS = ["1d"]

def download_and_save(symbol, interval="1d"):

    file_name = f"{symbol}_{interval}_{START_DATE}_{END_DATE}.feather"
    folder = ARCHIVE_DIR / symbol
    file_path = folder / file_name

    if file_path.exists():
        print(f"✅ {symbol} already cached.")
        return
    
    print(f"⬇️  Downloading {symbol} ({interval})...")
    df = yf.download(
        symbol,
        start=START_DATE,
        end=END_DATE,
        interval=interval,
        auto_adjust=False
    )
    if df is None or df.empty:
        print(f"⚠️  No usable data for {symbol}")
        return
    folder.mkdir(parents=True, exist_ok=True) 
    
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Adj Close": "adj_close", "Volume": "volume"
    })
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")

    df.columns = [str(col).lower() if isinstance(col, str) else "unknown" for col in df.columns]
    expected_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    if len(df.columns) != len(expected_columns):
        raise ValueError(f"Length mismatch: got {len(df.columns)} columns, expected {len(expected_columns)}")
    df.columns = expected_columns

    df = enrich_with_indicators_and_score(df, config)

    # Convert complex types to string before saving
    for col in ["ENTRY_BREAKDOWN"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else str(x) if x is not None else "")
    try:
        df.to_feather(file_path)
    except Exception as e:
        print(f"❌ Error saving {symbol}: {e}")
        return
    print(f"💾 Saved: {file_path.name}")

if __name__ == "__main__":
    failed = []
    for interval in INTERVALS:
        for symbol in ALL_SYMBOLS:
            try:
                download_and_save(symbol)
            except Exception as e:
                failed.append(symbol)
                print(f"❌ Fatal error for {symbol}: {e}")

    print(f"\n🎯 Completed with {len(failed)} failures out of {len(ALL_SYMBOLS)}")
    if failed:
        print("Failed symbols:", failed[:10])
