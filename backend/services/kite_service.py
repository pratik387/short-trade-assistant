import logging
from backend.services.data_fetcher import fetch_kite_data
from backend.services.technical_analysis import prepare_indicators, passes_hard_filters, calculate_score
from backend.services.config import load_filter_config, get_index_symbols

logger = logging.getLogger(__name__)

class KiteService:
    def __init__(self, interval: str = 'day', index: str = 'all'):
        from backend.authentication.kite_auth import set_access_token_from_file, validate_access_token
        set_access_token_from_file()
        if not validate_access_token():
            raise RuntimeError("Invalid Kite API token")
        self.interval = interval
        self.index = index
        cfg = load_filter_config()
        self.weights = cfg.get('score_weights', {})
        self.min_price = cfg.get('min_price', 50)
        self.min_volume = cfg.get('min_volume', 100000)

    def get_suggestions(self) -> list:
        instruments = get_index_symbols(self.index)
        suggestions, rsi_vals = [], []
        for item in instruments:
            df = fetch_kite_data(item['symbol'], item.get('instrument_token'), self.interval)
            if df.empty: continue
            df = prepare_indicators(df)
            latest = df.iloc[-1]
            if latest['close'] <= self.min_price or latest['volume'] < self.min_volume: continue
            cfg = load_filter_config()
            if not passes_hard_filters(latest, cfg): continue
            rsi_vals.append(latest['RSI'])
            score = calculate_score(latest, self.weights, sum(rsi_vals)/len(rsi_vals), candle_match=False)
            suggestions.append({
                'symbol': item['symbol'],
                'adx': round(float(latest['ADX_14']), 2),
                'dmp': round(float(latest['DMP_14']), 2),
                'dmn': round(float(latest['DMN_14']), 2),
                'rsi': round(float(latest['RSI']), 2),
                'macd': round(float(latest['MACD']), 2),
                'macd_signal': round(float(latest['MACD_Signal']), 2),
                'bb': round(float(latest['BB_%B']), 2) if 'BB_%B' in latest else None,
                'stochastic_k': round(float(latest.get('stochastic_k', 0)), 2) if 'stochastic_k' in latest else None,
                'obv': round(float(latest.get('obv', 0)), 2) if 'obv' in latest else None,
                'atr': round(float(latest.get('atr', 0)), 2) if 'atr' in latest else None,
                'stop_loss': round(latest['close'] * 0.97, 2),
                'score': score,
                'close': round(float(latest['close']), 2),
                'volume': int(latest['volume']),
            })
        return sorted(suggestions, key=lambda x: x['score'], reverse=True)[:12]

def get_filtered_stock_suggestions(interval: str = 'day', index: str = 'all') -> list:
    service = KiteService(interval, index)
    return service.get_suggestions()