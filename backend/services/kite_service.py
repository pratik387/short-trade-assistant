import pandas as pd
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
import json
from fastapi import APIRouter
from services.kite_auth import kite, set_access_token_from_file, validate_access_token
from services.adx_service import calculate_adx
from services.rsi_service import calculate_rsi
from services.bollinger_band_service import calculate_bollinger_bands
from services.macd_service import calculate_macd
from services.candle_pattern_service import is_bullish_engulfing, is_hammer

# Setup logger
logger = logging.getLogger("kite_service")

# Load environment variables (if needed)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

router = APIRouter()

# --- Stock suggestion logic ---

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

def _calculate_score(row):
    score = 0
    score += row['ADX_14'] > 25
    score += row['MACD'] > row['MACD_Signal']
    score += 0.2 < row['BB_%B'] < 0.8
    score += row['DMP_14'] > row['DMN_14']
    score += row.get('close', 0) > row.get('SMA_50', 0)
    return score

def get_filtered_stock_suggestions(interval: str = "day", index: str = "all"):
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
            logger.info(f"{symbol}: No instrument token, skipping.")
            continue

        df = fetch_kite_data(symbol, interval, token)
        if df.empty:
            logger.info(f"{symbol}: No historical data fetched.")
            continue

        df = _prepare_indicators(df)
        latest = df.iloc[-1]

        if latest['close'] <= 50.0:
            logger.info(f"{symbol}: Skipped due to low price ({latest['close']})")
            continue
        if latest['volume'] < 100000:
            logger.info(f"{symbol}: Skipped due to low volume ({latest['volume']})")
            continue
        if latest['EMA_20'] <= latest['EMA_50']:
            logger.info(f"{symbol}: Skipped due to EMA20 ({latest['EMA_20']}) <= EMA50 ({latest['EMA_50']})")
            continue

        required_cols = ['ADX_14', 'DMP_14', 'DMN_14', 'RSI', 'MACD', 'MACD_Signal', 'BB_%B']
        missing_cols = [col for col in required_cols if col not in df.columns or pd.isna(df[col].iloc[-1])]
        if missing_cols:
            logger.info(f"{symbol}: Dropped due to missing or sparse columns: {missing_cols}")
            continue

        rsi_values.append(latest['RSI'])
        score = _calculate_score(latest)

        if is_bullish_engulfing(df.tail(2)) or is_hammer(df.tail(1)):
            logger.info(f"{symbol}: Candlestick pattern match")
            score += 1

        stop_loss = round(latest['close'] * 0.97, 2)

        logger.info(f"{symbol}: Score={score}, ADX={latest['ADX_14']}, RSI={latest['RSI']}, MACD={latest['MACD']}, BB%={latest['BB_%B']}, Volume={latest['volume']}")

        suggestions.append({
            "symbol": symbol,
            "adx": round(float(latest['ADX_14']), 2),
            "dmp": round(float(latest['DMP_14']), 2),
            "dmn": round(float(latest['DMN_14']), 2),
            "rsi": round(float(latest['RSI']), 2),
            "macd": round(float(latest['MACD']), 2),
            "macd_signal": round(float(latest['MACD_Signal']), 2),
            "bb": round(float(latest['BB_%B']), 2),
            "volume": int(latest['volume']),
            "close": round(float(latest['close']), 2),
            "stop_loss": round(float(stop_loss), 2),
            "score": int(score),
            "category": ""
        })

    if not rsi_values:
        return []

    avg_rsi = sum(rsi_values) / len(rsi_values)
    for s in suggestions:
        if s['rsi'] > avg_rsi:
            s['score'] += 1
        s['category'] = (
            "momentum" if s['adx'] > 25 and s['macd'] > s['macd_signal'] else
            "reversal" if s['rsi'] < 40 and s['bb'] < 0.2 else
            "breakout" if s['bb'] > 0.85 else
            "swing"
        )

    from collections import defaultdict
    grouped = defaultdict(list)
    for s in sorted(suggestions, key=lambda x: x['score'], reverse=True):
        if len(grouped[s['category']]) < 3:
            grouped[s['category']].append(s)

    final = []
    for group in grouped.values():
        final.extend(group)

    logger.info(f"✅ Final list prepared with {len(final)} suggestions out of {len(instruments)} stocks")
    return final
