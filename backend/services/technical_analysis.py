import pandas as pd
from backend.services.filters.adx_filter import calculate_adx
from backend.services.filters.rsi_filter import calculate_rsi
from backend.services.filters.bollinger_band_filter import calculate_bollinger_bands
from backend.services.filters.macd_filter import calculate_macd
from backend.services.filters.stochastic_filter import calculate_stochastic
from backend.services.filters.obv_filter import calculate_obv
from backend.services.filters.atr_filter import calculate_atr
from backend.services.filters.fibonacci_filter import calculate_fibonacci_levels, is_fibonacci_support_zone


def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df = calculate_bollinger_bands(df)
    df = calculate_macd(df)
    df = df.join(calculate_adx(df[['high', 'low', 'close']]))
    r = calculate_rsi(df[['close']])
    df['RSI'] = r['RSI'] if isinstance(r, pd.DataFrame) else r
    df = df.join(calculate_stochastic(df))
    df = df.join(calculate_obv(df))
    df = df.join(calculate_atr(df))
        # Compute fibonacci levels per row over a rolling window of closes
    fib_levels = []
    for idx in range(len(df)):
        window = df['close'].iloc[max(0, idx-19): idx+1]
        if len(window) >= 2:
            fib_levels.append(calculate_fibonacci_levels(window))
        else:
            fib_levels.append({})
    df['fibonacci_levels'] = fib_levels

    return df


def passes_hard_filters(latest: pd.Series, cfg: dict) -> bool:
    if latest['ADX_14'] < cfg.get('adx_threshold', 30): return False
    if not (cfg.get('rsi_min', 40) <= latest['RSI'] <= cfg.get('rsi_max', 80)): return False
    if latest['MACD'] <= latest['MACD_Signal']: return False
    if latest['DMP_14'] <= latest['DMN_14']: return False
    if not is_fibonacci_support_zone(latest['close'], latest['fibonacci_levels']): return False
    return True


def calculate_score(latest: pd.Series, weights: dict, avg_rsi: float, candle_match: bool) -> int:
    score = 0
    if latest['ADX_14'] >= weights.get('adx', 3): score += weights['adx']
    if latest['MACD'] > latest['MACD_Signal']: score += weights.get('macd', 3)
    if weights.get('bb_lower', 0.2) < latest['BB_%B'] < weights.get('bb_upper', 0.8): score += weights.get('bb', 1)
    if latest['DMP_14'] > latest['DMN_14']: score += weights.get('dmp_dmn', 1)
    if latest['close'] > latest['SMA_50']: score += weights.get('price_sma', 2)
    if latest['RSI'] > avg_rsi: score += weights.get('rsi_above_avg', 1)
    if latest.get('stochastic_k', 0) > 50: score += weights.get('stochastic', 2)
    if latest.get('obv', 0) > 0: score += weights.get('obv', 2)
    if latest.get('atr', 0) > 0: score += weights.get('atr', 1)
    if candle_match: score += weights.get('candle_pattern', 2)
    return score