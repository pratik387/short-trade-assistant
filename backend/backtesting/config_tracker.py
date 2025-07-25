import hashlib
import json
from pathlib import Path

CONFIG_FILES = [
    Path("backend/config/filters_config.json"),
    Path("backend/config/exit_config.json")
]

CACHE_DIR = Path(".score_cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_combined_config_hash():
    combined = ""
    for path in CONFIG_FILES:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            combined += json.dumps(data, sort_keys=True)
    return hashlib.md5(combined.encode()).hexdigest()

def get_hash_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}_config.hash"

def is_config_stale(symbol: str) -> bool:
    hash_path = get_hash_path(symbol)
    current = get_combined_config_hash()
    if not hash_path.exists():
        return True
    cached = hash_path.read_text().strip()
    return current != cached

def update_config_hash(symbol: str):
    hash_path = get_hash_path(symbol)
    current = get_combined_config_hash()
    hash_path.write_text(current)
