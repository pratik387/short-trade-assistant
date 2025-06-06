from tinydb import TinyDB
from pathlib import Path

DB_DIR = Path(__file__).resolve().parents[1] / "db" / "tables"
DB_DIR.mkdir(parents=True, exist_ok=True)

_table_cache = {}

def get_table(name: str) -> TinyDB:
    """Returns a TinyDB table instance from /db/tables/{name}.json"""
    if name in _table_cache:
        return _table_cache[name]

    path = DB_DIR / f"{name}.json"
    db = TinyDB(str(path))
    _table_cache[name] = db
    return db
