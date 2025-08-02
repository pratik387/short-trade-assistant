# factories/broker_factory.py

from brokers.kite.kite_broker import KiteBroker
from brokers.mock.mock_broker import MockBroker
from config.logging_config import get_loggers

logger, _ = get_loggers()

def get_broker(name: str, config: dict):
    try:
        if name == "kite":
            return KiteBroker(config)
        elif name == "mock":
            return MockBroker(config)
        else:
            raise ValueError(f"Unknown broker: {name}")
    except Exception as e:
        logger.error(f"❌ Failed to load broker '{name}': {e}")
        return None
