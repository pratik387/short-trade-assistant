import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
INDEX_DIR = Path(__file__).resolve().parents[2] / "assets" / "indexes"

def get_index_symbols(index: str) -> list:
    """
    Load NSE index symbol lists (all, nifty_50, nifty_100, etc.)
    """
    file_map = {
        "all": "nse_all.json",
        "nifty_50": "nifty_50.json",
        "nifty_100": "nifty_100.json",
        "nifty_200": "nifty_200.json",
        "nifty_500": "nifty_500.json",
    }
    file_name = file_map.get(index, file_map["all"])
    path = INDEX_DIR / file_name

    if not path.exists():
        logger.warning(f"Index file not found: {path}")
        return []

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading index file {path}: {e}")
        return []
