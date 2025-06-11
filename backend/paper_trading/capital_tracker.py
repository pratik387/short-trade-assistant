import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CAPITAL_FILE = Path(__file__).resolve().parent / "capital.json"
INITIAL_CAPITAL = 100000

def get_available_capital():
    if not CAPITAL_FILE.exists():
        logger.info(f"No capital file found. Initializing with ₹{INITIAL_CAPITAL}.")
        try:
            with open(CAPITAL_FILE, "w") as f:
                json.dump({"available": INITIAL_CAPITAL}, f)
        except Exception as e:
            logger.error(f"Failed to create capital file: {e}")
            raise

    try:
        with open(CAPITAL_FILE, "r") as f:
            data = json.load(f)
            return data.get("available", INITIAL_CAPITAL)
    except Exception as e:
        logger.error(f"Failed to read capital file: {e}")
        raise

def update_capital(delta):
    try:
        current = get_available_capital()
        new_capital = max(0, current + delta)  # Optional: prevent negative balance
        with open(CAPITAL_FILE, "w") as f:
            json.dump({"available": new_capital}, f)
        logger.info(f"💰 Capital updated: {current} -> {new_capital} (Δ {delta})")
    except Exception as e:
        logger.error(f"Failed to update capital: {e}")
        raise
