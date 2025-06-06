import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "filters_config.json"

# Optional: define expected keys and defaults for safety
REQUIRED_KEYS = [
    "adx_threshold", "score_weights", "exit_strategy", "exit_criteria"
]

def load_filter_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing filters_config.json at {CONFIG_PATH}")

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    missing_keys = [k for k in REQUIRED_KEYS if k not in config]
    if missing_keys:
        raise KeyError(f"filters_config.json is missing required keys: {missing_keys}")

    return config

# Optional: quick test
if __name__ == "__main__":
    cfg = load_filter_config()
    print("Config loaded successfully. Keys:", list(cfg.keys()))
