
import os
import json
from datetime import datetime

SUGGESTIONS_DIR = "backend/cache/suggestions"

def get_suggestions_file_path(index: str):
    today = datetime.now().strftime("%Y-%m-%d")
    safe_index = index.replace(" ", "_").lower()
    return os.path.join(SUGGESTIONS_DIR, f"suggestions_{safe_index}_{today}.json")

def store_suggestions_file(suggestions: list, index: str):
    os.makedirs(SUGGESTIONS_DIR, exist_ok=True)
    path = get_suggestions_file_path(index)
    with open(path, "w") as f:
        json.dump(suggestions, f, indent=2)

def load_suggestions_file(index: str) -> list:
    path = get_suggestions_file_path(index)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def suggestions_file_exists(index: str) -> bool:
    path = get_suggestions_file_path(index)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return bool(data)  # True if list/dict is non-empty
    except Exception:
        return False

