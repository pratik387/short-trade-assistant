import os
import yfinance as yf
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# Directory to save CSVs
CACHE_DIR = Path(__file__).resolve().parent / "ohlcv_cache"
CACHE_DIR.mkdir(exist_ok=True)

# Define symbols to download
INDEX_FILE = Path(__file__).resolve().parents[1] / "assets" / "indexes" / "nifty_500.json"
with open(INDEX_FILE) as f:
    data = json.load(f)
    NIFTY_500_SYMBOLS = [entry["symbol"] for entry in data]

# Date range
START_DATE = "2024-01-02"
END_DATE = "2025-06-19"

def download_and_save(symbol):
    try:
        file_path = CACHE_DIR / f"{symbol}.csv"
        if file_path.exists():
            print(f"✅ {symbol} already cached.")
            return

        print(f"⬇️  Downloading {symbol}...")
        df = yf.download(
            symbol,
            start=START_DATE,
            end=END_DATE,
            interval="1d",
            auto_adjust=False
        )
        if df.empty:
            print(f"⚠️ No data found for {symbol}")
            return

        # Clean and normalize column names
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume"
        })

        df.index.name = "date"  # Make sure index has a name before reset_index
        df = df.reset_index()
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')  # Make timezone-aware

        # Force first column name to be 'date'

        df.columns = [str(col).lower() if isinstance(col, str) else "unknown" for col in df.columns]
        expected_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
        if len(df.columns) != len(expected_columns):
            raise ValueError(f"Length mismatch: got {len(df.columns)} columns, expected {len(expected_columns)}")
        df.columns = expected_columns

        df.to_csv(file_path, index=False)
        print(f"💾 Saved: {file_path.name}")

    except Exception as e:
        print(f"❌ Error downloading {symbol}: {e}")

if __name__ == "__main__":
    for symbol in NIFTY_500_SYMBOLS:
        download_and_save(symbol)
