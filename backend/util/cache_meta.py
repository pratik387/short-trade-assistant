# cache_meta.py

import os
import json
from datetime import datetime
from typing import Dict

META_FILENAME = "cache_meta.json"

def get_meta_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, META_FILENAME)

def load_cache_meta(cache_dir: str) -> Dict[str, str]:
    meta_path = get_meta_path(cache_dir)
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f)
    return {}

def save_cache_meta(cache_dir: str, meta: Dict[str, str]) -> None:
    meta_path = get_meta_path(cache_dir)
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

def update_cache_meta(cache_dir: str, symbol: str, last_candle_time: datetime) -> None:
    meta = load_cache_meta(cache_dir)
    meta[symbol] = last_candle_time.strftime("%Y-%m-%dT%H:%M:%S")
    save_cache_meta(cache_dir, meta)

def get_last_updated_time(cache_dir: str, symbol: str) -> datetime:
    meta = load_cache_meta(cache_dir)
    ts = meta.get(symbol)
    if ts:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
    return datetime.min
