import pandas as pd
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from services.kite_auth import kite, TOKEN_FILE
from services.adx_service import calculate_adx
from services.rsi_service import calculate_rsi
from services.bollinger_band_service import calculate_bollinger_bands
from services.macd_service import calculate_macd

# Setup logger
logger = logging.getLogger("kite_service")

# Load environment variables (if needed)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# Set access token from saved file
def set_access_token_from_file():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            kite.set_access_token(token)
            logger.info("Access token loaded from file")
    else:
        logger.warning("Access token file not found")

# Validate token with retry once
def validate_access_token():
    try:
        profile = kite.profile()
        logger.info(f"Kite access verified for user: {profile['user_name']}")
        return True
    except Exception as e:
        logger.warning(f"Initial token validation failed: {e}. Retrying...")
        set_access_token_from_file()
        try:
            profile = kite.profile()
            logger.info(f"Token revalidated successfully for user: {profile['user_name']}")
            return True
        except Exception as e2:
            logger.error(f"Access token invalid after retry: {e2}. Please login via Zerodha to refresh token.")
            return False

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

# Fetch historical data from Kite with retry

def fetch_kite_data(symbol: str, interval: str = "day", instrument_token: int = None):
    if not instrument_token:
        logger.error(f"Instrument token is missing for {symbol}")
        return pd.DataFrame()

    if interval in ["5minute", "15minute"]:
        from_date = datetime.today() - timedelta(days=10)
    elif interval == "day":
        from_date = datetime.today() - timedelta(days=60)
    else:
        from_date = datetime.today() - timedelta(days=180)

    to_date = datetime.today()

    df = _fetch_historical(symbol, from_date, to_date, interval, instrument_token)
    if df.empty:
        logger.warning(f"Kite fetch failed for {symbol}. Retrying after refreshing token...")
        set_access_token_from_file()
        df = _fetch_historical(symbol, from_date, to_date, interval, instrument_token)

    return df

# Combined function to return filtered stock suggestions with indicators

def get_filtered_stock_suggestions(interval: str = "day"):
    set_access_token_from_file()
    if not validate_access_token():
        return []

    suggestions = []
    try:
        instruments = kite.instruments("NSE")
        seen = set()
        for ins in instruments:
            tradingsymbol = ins.get("tradingsymbol")
            instrument_token = ins.get("instrument_token")

            if (
                ins.get("instrument_type") == "EQ"
                and ins.get("segment") == "NSE"
                and tradingsymbol.isalpha()
                and tradingsymbol not in seen
            ):
                symbol = tradingsymbol + ".NS"
                seen.add(tradingsymbol)

                df = fetch_kite_data(symbol, interval=interval, instrument_token=instrument_token)
                if df.empty:
                    continue

                close_price = df['close'].iloc[-1] if 'close' in df.columns else 0.0
                if close_price <= 20.0:
                    continue

                df = df.rename(columns={"Adj Close": "Adj_Close"})
                adx_df = calculate_adx(df[['high', 'low', 'close']])
                rsi_series = calculate_rsi(df[['close']])
                df = calculate_bollinger_bands(df)
                df = calculate_macd(df)

                if adx_df is not None and isinstance(adx_df, pd.DataFrame):
                    adx_df.index = df.index
                    df = df.join(adx_df)

                if rsi_series is not None:
                    if isinstance(rsi_series, pd.Series):
                        df["RSI"] = rsi_series
                    elif isinstance(rsi_series, pd.DataFrame) and "RSI" in rsi_series.columns:
                        df = df.join(rsi_series[["RSI"]])

                df = df.dropna(subset=['ADX_14', 'DMP_14', 'DMN_14', 'RSI', 'MACD', 'MACD_Signal', 'BB_%B'])
                if df.empty:
                    continue

                latest = df.iloc[-1]
                score = 0
                if latest['ADX_14'] > 25:
                    score += 1
                if 45 < latest['RSI'] < 65:
                    score += 1
                if latest['MACD'] > latest['MACD_Signal']:
                    score += 1
                if 0.2 < latest['BB_%B'] < 0.8:
                    score += 1
                if latest['DMP_14'] > latest['DMN_14']:
                    score += 1

                if score >= 3:
                    category = "momentum" if latest['ADX_14'] > 25 and latest['MACD'] > latest['MACD_Signal'] else (
                        "reversal" if latest['RSI'] < 40 and latest['BB_%B'] < 0.2 else (
                        "breakout" if latest['BB_%B'] > 0.85 else "swing"))

                    volume = int(latest['volume']) if 'volume' in latest else 0
                    stop_loss = round(close_price * 0.97, 2)
                    suggestions.append({
                        "symbol": symbol,
                        "adx": round(latest['ADX_14'], 2),
                        "dmp": round(latest['DMP_14'], 2),
                        "dmn": round(latest['DMN_14'], 2),
                        "rsi": round(latest['RSI'], 2),
                        "macd": round(latest['MACD'], 2),
                        "macd_signal": round(latest['MACD_Signal'], 2),
                        "bb": round(latest['BB_%B'], 2),
                        "volume": volume,
                        "close": round(close_price, 2),
                        "stop_loss": stop_loss,
                        "score": score,
                        "category": category
                    })

    except Exception as e:
        logger.error(f"Error processing instruments: {e}")

    from collections import defaultdict
    grouped = defaultdict(list)
    for s in sorted(suggestions, key=lambda x: x['score'], reverse=True):
        if len(grouped[s['category']]) < 3:
            grouped[s['category']].append(s)

    final = []
    for group in grouped.values():
        final.extend(group)

    return final
