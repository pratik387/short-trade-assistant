import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Paths to configuration and data files
BASE_DIR = Path(__file__).resolve().parents[1]
FILTER_CONFIG_PATH = BASE_DIR / "config" / "filters_config.json"
DATA_DIR = BASE_DIR / "data"


def load_filter_config() -> dict:
    """
    Load filter thresholds, weights, and other settings from JSON.
    """
    try:
        with open(FILTER_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load filter config: {e}")
        return {}


def get_index_symbols(index: str) -> list:
    """
    Load NSE index symbol lists (all, nifty_50, nifty_100, etc.)
    """
    file_map = {
        "all": DATA_DIR / "nse_all.json",
        "nifty_50": DATA_DIR / "nifty_50.json",
        "nifty_100": DATA_DIR / "nifty_100.json",
        "nifty_200": DATA_DIR / "nifty_200.json",
        "nifty_500": DATA_DIR / "nifty_500.json",
    }
    path = file_map.get(index, file_map['all'])
    if not path.exists():
        logger.warning(f"Index file not found: {path}")
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading index file {path}: {e}")
        return []