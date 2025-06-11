import logging
from tinydb import TinyDB
from pathlib import Path

# Logger setup
logger = logging.getLogger(__name__)

# Directory to store TinyDB tables
DB_DIR = Path(__file__).resolve().parents[1] / "db" / "tables"
DB_DIR.mkdir(parents=True, exist_ok=True)

# Cache for open table instances
_table_cache = {}

def get_table(name: str) -> TinyDB:
    """
    Returns a TinyDB table instance from /db/tables/{name}.json.
    Logs any loading issues or reuse of cached connections.
    """
    if name in _table_cache:
        logger.debug(f"Using cached TinyDB table for: {name}")
        return _table_cache[name]

    path = DB_DIR / f"{name}.json"
    try:
        db = TinyDB(str(path))
        _table_cache[name] = db
        logger.info(f"✅ Loaded TinyDB table: {path}")
        return db
    except Exception as e:
        logger.exception(f"❌ Failed to load TinyDB table: {path}")
        raise
