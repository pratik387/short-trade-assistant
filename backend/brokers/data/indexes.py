import json
from pathlib import Path
import logging

logger = logging.getLogger("index_loader")

DATA_DIR = Path(__file__).resolve().parents[2] / "assets/indexes"

FILE_MAP = {
    "all": "nse_all.json",
    "nifty_50": "nifty_50.json",
    "nifty_100": "nifty_100.json",
    "nifty_200": "nifty_200.json",
    "nifty_500": "nifty_500.json"
}

def get_index_symbols(index: str) -> list:
    """
    Load instrument data for a given index (e.g., nifty_50).
    """
    filename = FILE_MAP.get(index)
    if not filename:
        logger.warning(f"Unknown index '{index}'. Falling back to 'all'.")
        filename = FILE_MAP["all"]

    path = DATA_DIR / filename
    if not path.exists():
        logger.warning(f"Index file not found for '{index}': {path}")
        return []

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load index data from {path}: {e}")
        return []

def get_token_for_symbol(symbol: str) -> int:
    """
    Look up instrument token for a given symbol from the full NSE list.
    """
    all_path = DATA_DIR / FILE_MAP["all"]
    if not all_path.exists():
        logger.warning(f"Instrument list file missing: {all_path}")
        return None

    try:
        with open(all_path, "r") as f:
            instruments = json.load(f)
        for item in instruments:
            if item.get("symbol") == symbol:
                return item.get("instrument_token")
    except Exception as e:
        logger.error(f"Error resolving token for {symbol}: {e}")

    return None
