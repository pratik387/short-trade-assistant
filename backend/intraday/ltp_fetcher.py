import time
from brokers.kite.kite_broker import KiteBroker
from config.logging_config import get_loggers

logger, _ = get_loggers()


def batch_symbols(symbols, batch_size=100):
    for i in range(0, len(symbols), batch_size):
        yield symbols[i:i + batch_size]


def fetch_ltp_for_symbols(symbols, index="all"):
    broker = KiteBroker()
    symbol_map = broker.get_symbols(index)
    symbol_lookup = {item["symbol"]: item["symbol"] for item in symbol_map}

    ltp_data = {}
    for batch in batch_symbols(symbols):
        try:
            kite_symbols = [f"NSE:{symbol_lookup[symbol]}" for symbol in batch if symbol in symbol_lookup]
            response = broker.get_ltp_batch(kite_symbols)
            for k, v in response.items():
                symbol = k.split(":")[-1]
                ltp_data[symbol] = v
            time.sleep(0.25)
        except Exception as e:
            logger.error(f"❌ LTP fetch failed for batch: {batch} | Error: {e}")

    return ltp_data


if __name__ == "__main__":
    broker = KiteBroker()
    all_symbols = [item["symbol"] for item in broker.get_symbols("all")]
    ltp_map = fetch_ltp_for_symbols(all_symbols)
    print("✅ LTPs fetched for:", len(ltp_map), "symbols")
