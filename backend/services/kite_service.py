import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
import logging
import json
from fastapi import APIRouter

from backend.authentication.kite_auth import kite, set_access_token_from_file, validate_access_token
from backend.services.filters.adx_filter import calculate_adx
from backend.services.filters.rsi_filter import calculate_rsi
from backend.services.filters.bollinger_band_filter import calculate_bollinger_bands
from backend.services.filters.macd_filter import calculate_macd
from backend.services.filters.candle_pattern_filter import is_bullish_engulfing, is_hammer
from backend.services.filters.stochastic_filter import calculate_stochastic
from backend.services.filters.obv_filter import calculate_obv
from backend.services.filters.atr_filter import calculate_atr

# Setup logger
logger = logging.getLogger("kite_service")

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

router = APIRouter()

FILTER_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "filters_config.json"


def load_filter_config():
    try:
        with open(FILTER_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load filter config: {e}")
        return {}


def get_index_symbols(index: str) -> list:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"
    file_map = {
        "all": DATA_DIR / "nse_all.json",
        "nifty_50": DATA_DIR / "nifty_50.json",
        "nifty_100": DATA_DIR / "nifty_100.json",
        "nifty_200": DATA_DIR / "nifty_200.json",
        "nifty_500": DATA_DIR / "nifty_500.json",
    }
    file_path = file_map.get(index, file_map["all"])
    if not file_path.exists():
        logger.warning(f"⚠️ Index file not found for: {index}")
        return []
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Failed reading index file {file_path}: {e}")
        return []

def passes_hard_filters(row, config):
    if row['ADX_14'] < config.get("adx_threshold", 30):
        return False
    if not (config.get("rsi_min", 40) <= row['RSI'] <= config.get("rsi_max", 80)):
        return False
    if row['MACD'] <= row['MACD_Signal']:
        return False
    if row['DMP_14'] <= row['DMN_14']:
        return False
    return True


def _fetch_historical(symbol, from_date, to_date, interval, token):
    try:
        historical = kite.historical_data(
            instrument_token=token,
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )
        df = pd.DataFrame(historical)
        if not df.empty:
            df.set_index("date", inplace=True)
            df = df.join(calculate_stochastic(df))
        df = df.join(calculate_obv(df))
        df = df.join(calculate_atr(df))
        return df
    except Exception as e:
        logger.error(f"Fetch failed for {symbol}: {e}")
        return pd.DataFrame()


def fetch_kite_data(symbol: str, interval: str = "day", instrument_token: int = None):
    if not instrument_token:
        logger.error(f"Instrument token is missing for {symbol}")
        return pd.DataFrame()

    to_date = datetime.today()
    if to_date.weekday() >= 5:
        to_date -= timedelta(days=to_date.weekday() - 4)

    from_date = to_date - timedelta(days=100 if interval == "day" else 10 if interval in ["5minute", "15minute"] else 180)

    try:
        return _fetch_historical(symbol, from_date, to_date, interval, instrument_token)
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Fetch failed for {symbol}: {e}")

        if "token" in error_msg or "invalid" in error_msg or "unauthorized" in error_msg:
            logger.warning(f"{symbol}: Token-related issue. Retrying after refreshing token...")
            set_access_token_from_file()
            try:
                return _fetch_historical(symbol, from_date, to_date, interval, instrument_token)
            except Exception as e2:
                logger.error(f"{symbol}: Retry failed after token refresh: {e2}")
        elif "too many requests" in error_msg:
            logger.warning(f"{symbol}: Skipping due to API rate limit (429 Too Many Requests)")
        else:
            logger.warning(f"{symbol}: Skipping due to unknown error")

    return pd.DataFrame()

def _prepare_indicators(df):
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df = calculate_bollinger_bands(df)
    df = calculate_macd(df)
    df = df.join(calculate_adx(df[['high', 'low', 'close']]))
    rsi_series = calculate_rsi(df[['close']])
    if isinstance(rsi_series, pd.Series):
        df["RSI"] = rsi_series
    elif isinstance(rsi_series, pd.DataFrame) and "RSI" in rsi_series.columns:
        df = df.join(rsi_series[["RSI"]])
    return df


def _calculate_score(row, weights, config, avg_rsi=None, candle_match=False):
    score = 0
    adx_threshold = config.get("adx_threshold", 30)
    bb_lower = config.get("bb_lower", 0.2)
    bb_upper = config.get("bb_upper", 0.8)

    if row['ADX_14'] >= adx_threshold:
        score += weights.get("adx", 1)
    if row['MACD'] > row['MACD_Signal']:
        score += weights.get("macd", 1)
    if bb_lower < row['BB_%B'] < bb_upper:
        score += weights.get("bb", 1)
    if row['DMP_14'] > row['DMN_14']:
        score += weights.get("dmp_dmn", 1)
    if row.get('close', 0) > row.get('SMA_50', 0):
        score += weights.get("price_sma", 1)
    if avg_rsi is not None and row['RSI'] > avg_rsi:
        score += weights.get("rsi_above_avg", 1)
    if row.get('stochastic_k', 0) > 50:
        score += weights.get("stochastic", 1)
    if row.get('obv', 0) > 0:
        score += weights.get("obv", 1)
    if row.get('atr', 0) > 0:
        score += weights.get("atr", 1)
    if candle_match:
        score += weights.get("candle_pattern", 1)

    return score


def get_filtered_stock_suggestions(interval: str = "day", index: str = "all"):
    config = load_filter_config()
    weights = config.get("score_weights", {
        "adx": 3,
        "macd": 3,
        "bb": 1,
        "dmp_dmn": 1,
        "price_sma": 2,
        "candle_pattern": 2,
        "rsi_above_avg": 1,
        "stochastic": 2,
        "obv": 2,
        "atr": 1
    })
    min_price = config.get("min_price", 50)
    min_volume = config.get("min_volume", 100000)

    set_access_token_from_file()
    if not validate_access_token():
        return []

    instruments = get_index_symbols(index)
    if not instruments:
        logger.warning("No instruments found for the selected index.")
        return []

    suggestions = []
    rsi_values = []

    for item in instruments:
        symbol = item["symbol"]
        token = item.get("instrument_token")

        if not token:
            continue

        df = fetch_kite_data(symbol, interval, token)
        if df.empty:
            continue

        df = _prepare_indicators(df)
        latest = df.iloc[-1]

        if latest['close'] <= min_price or latest['volume'] < min_volume or latest['EMA_20'] <= latest['EMA_50']:
            continue

        required_cols = ['ADX_14', 'DMP_14', 'DMN_14', 'RSI', 'MACD', 'MACD_Signal', 'BB_%B']
        if any(col not in df.columns or pd.isna(df[col].iloc[-1]) for col in required_cols):
            continue

        # Strict filter: must meet both ADX and RSI criteria
        if not passes_hard_filters(latest, config):
            continue

        rsi_values.append(latest['RSI'])
        candle_match = is_bullish_engulfing(df.tail(2)) or is_hammer(df.tail(1))
        score = _calculate_score(latest, weights, config, candle_match=candle_match)

        stop_loss = round(latest['close'] * 0.97, 2)

        suggestions.append({
            "symbol": symbol,
            "adx": round(float(latest['ADX_14']), 2),
            "dmp": round(float(latest['DMP_14']), 2),
            "dmn": round(float(latest['DMN_14']), 2),
            "rsi": round(float(latest['RSI']), 2),
            "macd": round(float(latest['MACD']), 2),
            "macd_signal": round(float(latest['MACD_Signal']), 2),
            "bb": round(float(latest['BB_%B']), 2),
            "stochastic_k": round(float(latest.get('stochastic_k', 0)), 2),
            "obv": round(float(latest.get('obv', 0)), 2),
            "atr": round(float(latest.get('atr', 0)), 2),
            "volume": int(latest['volume']),
            "close": round(float(latest['close']), 2),
            "stop_loss": stop_loss,
            "score": score
        })


    if not rsi_values:
        return []

    avg_rsi = sum(rsi_values) / len(rsi_values)
    for s in suggestions:
        row_like = {
            'ADX_14': s['adx'],
            'MACD': s['macd'],
            'MACD_Signal': s['macd_signal'],
            'BB_%B': s['bb'],
            'DMP_14': s['dmp'],
            'DMN_14': s['dmn'],
            'close': s['close'],
            'SMA_50': s['close'],  # Approximate fallback if actual SMA_50 not stored
            'RSI': s['rsi'],
            'stochastic_k': s.get('stochastic_k', 0),
            'obv': s.get('obv', 0),
            'atr': s.get('atr', 0)
        }
        s['score'] = _calculate_score(row_like, weights, config, avg_rsi=avg_rsi)

    top_stocks = sorted(suggestions, key=lambda x: (x['score'], x['rsi'], x['volume']), reverse=True)[:12]

    logger.info(f"✅ Top {len(top_stocks)} suggestions selected from {len(instruments)} stocks")
    return top_stocks
