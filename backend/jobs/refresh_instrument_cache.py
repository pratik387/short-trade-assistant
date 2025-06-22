# @role: Background job to refresh instrument metadata (symbols, expiry)
# @used_by: cache_router.py
# @filter_type: system
# @tags: job, cache, instrument
import requests
import pandas as pd
import json
from pathlib import Path
from io import StringIO
import logging
from exceptions.exceptions import InvalidTokenException
from util.util import retry

from routes.kite_auth_router import kite

logger = logging.getLogger("index_refresher")

DATA_DIR = Path(__file__).resolve().parents[1] / "assets/indexes"
DATA_DIR.mkdir(exist_ok=True)

INDEX_CSV_URLS = {
    "nifty_50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "nifty_100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "nifty_200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "nifty_500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
}

@retry()
def is_symbol_valid(symbol: str, token: int) -> bool:
    try:
        kite.historical_data(instrument_token=token, interval="day", from_date="2025-01-01", to_date="2025-01-02")
        return True
    except Exception as e:
        err_msg = str(e).lower()
        if any(t in err_msg for t in ['api_key', 'access_token']):
            raise InvalidTokenException(err_msg)
        else: 
            raise
    
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
                symbol = tradingsymbol + ".NS"
                instrument_map[tradingsymbol] = {
                    "symbol": symbol,
                    "instrument_token": ins["instrument_token"],
                }

        # Filter invalid symbols
        validated = {
            sym: meta
            for sym, meta in instrument_map.items()
            if is_symbol_valid(meta["symbol"], meta["instrument_token"])
        }

        all_path = DATA_DIR / "nse_all.json"
        with open(all_path, "w") as f:
            json.dump(list(validated.values()), f, indent=2)
        logger.info(f"✅ Saved full NSE instrument list: {len(validated)}")
        counts = {"all": len(validated)}

        for index_name, csv_url in INDEX_CSV_URLS.items():
            try:
                res = requests.get(csv_url, headers={"User-Agent": "Mozilla/5.0"})
                res.raise_for_status()
                df = pd.read_csv(StringIO(res.text))
                symbols = df["Symbol"].dropna().tolist()

                filtered = [
                    validated[sym]
                    for sym in symbols
                    if sym in validated
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

if __name__ == "__main__":
    print(refresh_index_cache())
