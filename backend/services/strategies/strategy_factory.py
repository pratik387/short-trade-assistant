# factories/strategy_factory.py

import importlib
from config.logging_config import get_loggers

logger, _ = get_loggers()

def get_strategy(name: str, config: dict):
    try:
        module_path = f"services.strategies.{name}_strategy"
        class_name = f"{name.capitalize()}Strategy"

        strategy_module = importlib.import_module(module_path)
        strategy_class = getattr(strategy_module, class_name)

        return strategy_class(config)
    except (ModuleNotFoundError, AttributeError) as e:
        logger.error(f"❌ Failed to load strategy '{name}': {e}")
        return None
