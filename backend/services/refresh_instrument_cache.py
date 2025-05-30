import requests
import pandas as pd
import json
from pathlib import Path
from io import StringIO
from backend.authentication.kite_auth import kite
import logging

logger = logging.getLogger("index_refresher")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

INDEX_CSV_URLS = {
    "nifty_50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "nifty_100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "nifty_200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "nifty_500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
}

def refresh_index_cache():
    try:
        logger.info("Fetching all NSE instruments from Kite")
        instruments = kite.instruments("NSE")
        seen = set()
        instrument_map = {}

        for ins in instruments:
            tradingsymbol = ins.get("tradingsymbol", "")
            if (
                ins.get("instrument_type") == "EQ"
                and ins.get("segment") == "NSE"
                and tradingsymbol.isalpha()
                and tradingsymbol not in seen
            ):
                seen.add(tradingsymbol)
                instrument_map[tradingsymbol] = {
                    "symbol": tradingsymbol + ".NS",
                    "instrument_token": ins["instrument_token"]
                }

        # Save full list
        all_path = DATA_DIR / "nse_all.json"
        with open(all_path, "w") as f:
            json.dump(list(instrument_map.values()), f, indent=2)

        logger.info(f"✅ Saved full NSE instrument list: {len(instrument_map)}")
        counts = {"all": len(instrument_map)}

        # Loop through each index and save subset
        for index_name, csv_url in INDEX_CSV_URLS.items():
            try:
                res = requests.get(csv_url, headers={"User-Agent": "Mozilla/5.0"})
                res.raise_for_status()
                df = pd.read_csv(StringIO(res.text))
                symbols = df["Symbol"].dropna().tolist()

                filtered = [
                    instrument_map[sym]
                    for sym in symbols
                    if sym in instrument_map
                ]

                with open(DATA_DIR / f"{index_name}.json", "w") as f:
                    json.dump(filtered, f, indent=2)

                logger.info(f"✅ Saved {index_name}.json with {len(filtered)} stocks")
                counts[index_name] = len(filtered)

            except Exception as e:
                logger.warning(f"⚠️ Failed to process {index_name}: {e}")

        return {"status": "success", **counts}

    except Exception as e:
        logger.error(f"❌ Failed to refresh index cache: {e}")
        return {"status": "failed", "error": str(e)}

# Optional: make callable via CLI
if __name__ == "__main__":
    print(refresh_index_cache())
