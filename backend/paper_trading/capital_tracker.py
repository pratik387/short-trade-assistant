from pathlib import Path
import json

CAPITAL_FILE = Path(__file__).resolve().parent / "capital.json"
INITIAL_CAPITAL = 100000


def get_available_capital():
    if not CAPITAL_FILE.exists():
        with open(CAPITAL_FILE, "w") as f:
            json.dump({"available": INITIAL_CAPITAL}, f)
    with open(CAPITAL_FILE, "r") as f:
        return json.load(f)["available"]


def update_capital(delta):
    data = {"available": get_available_capital() + delta}
    with open(CAPITAL_FILE, "w") as f:
        json.dump(data, f)