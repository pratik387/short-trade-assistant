# @role: TinyDB client accessor
# @used_by: exit_job_runner.py, portfolio_router.py, suggestion_router.py, tick_listener.py
# @filter_type: utility
# @tags: tinydb, db, client
import os
from tinydb import TinyDB
from pathlib import Path

# Logger setup
from config.logging_config import get_loggers
logger, trade_logger = get_loggers()

# Directory to store TinyDB tables
DB_DIR = Path(__file__).resolve().parents[1] / "db" / "tinydb" / "tables"
DB_DIR.mkdir(parents=True, exist_ok=True)

# Cache for open table instances
_table_cache = {}

def get_table(name: str, use_mode: bool = True) -> TinyDB:
    """
    Returns a TinyDB table instance from /db/tinydb/tables/{name}_{mode}.json.
    If use_mode is False, loads from /db/tinydb/tables/{name}.json directly.
    """
    mode_suffix = f"_{os.getenv('TRADE_MODE', 'mock')}" if use_mode else ""
    full_name = f"{name}{mode_suffix}"

    if full_name in _table_cache:
        logger.debug(f"Using cached TinyDB table for: {full_name}")
        return _table_cache[full_name]

    path = DB_DIR / f"{full_name}.json"
    try:
        db = TinyDB(str(path))
        _table_cache[full_name] = db
        logger.info(f"✅ Loaded TinyDB table: {path}")
        return db
    except Exception as e:
        logger.exception(f"❌ Failed to load TinyDB table: {path}")
        raise