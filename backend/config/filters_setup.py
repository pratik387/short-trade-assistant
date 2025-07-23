# @role: Registers and configures available filter modules
# @used_by: exit_job_runner.py, suggestion_logic.py, suggestion_router.py
# @filter_type: utility
# @tags: filter, config, bootstrap
# config/filters.py

import json
from config.logging_config import get_loggers
from pathlib import Path

logger, trade_logger = get_loggers()
REQUIRED_KEYS = [
    "entry_filters",
    "exit_filters"
]

# Adjust path if your filters_config.json lives elsewhere
CONFIG_PATH = Path(__file__).resolve().parent / "filters_config.json"
EXIT_CONFIG_PATH = Path(__file__).resolve().parent / "exit_config.json"

def load_filters():
    if not CONFIG_PATH.exists():
        logger.error(f"Missing filters_config.json at {CONFIG_PATH}")
        raise FileNotFoundError(f"{CONFIG_PATH} not found")
    
    if not EXIT_CONFIG_PATH.exists():
        logger.error(f"Missing filters_config.json at {EXIT_CONFIG_PATH}")
        raise FileNotFoundError(f"{EXIT_CONFIG_PATH} not found")

    cfg = {}
    try:
        with CONFIG_PATH.open("r") as f:
            cfg.update(json.load(f))
    except Exception as e:
        logger.exception(f"Failed to load entry config: {e}")

    try:
        with EXIT_CONFIG_PATH.open("r") as f:
            cfg.update(json.load(f))  # Will override if any keys clash
    except Exception as e:
        logger.exception(f"Failed to load exit config: {e}")


    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        logger.error(f"filters_config.json missing keys: {missing}")
        raise KeyError(f"Missing keys in filters_config.json: {missing}")

    logger.info("✅ Loaded filters_config.json successfully.")
    return cfg

filters = load_filters()