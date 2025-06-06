from backend.services.entry_service import EntryService
from backend.brokers.kite.kite_data_provider import KiteDataProvider
from backend.config.settings import load_filter_config

def get_filtered_stock_suggestions(interval: str = "day", index: str = "nifty_50") -> list:
    provider = KiteDataProvider(interval=interval, index=index)
    config = load_filter_config()
    service = EntryService(data_provider=provider, config=config)
    return service.get_suggestions()
