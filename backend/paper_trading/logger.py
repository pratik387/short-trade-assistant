from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent / "paper_trades.log"


def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")