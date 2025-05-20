from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from email_alert import send_exit_email
import yfinance as yf
import pandas as pd
import logging
from services.adx_service import calculate_adx
from services.rsi_service import calculate_rsi

app = FastAPI()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("main")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/send-exit-email")
async def trigger_exit_email(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    if symbol:
        logger.info(f"Triggering exit email for {symbol}")
        send_exit_email(symbol)
        return {"status": "email sent"}
    logger.warning("No symbol received for exit email")
    return {"status": "symbol missing"}

@app.get("/api/short-term-suggestions")
def get_short_term_suggestions():
    stock_list = [
        "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "HDFC.NS", "KOTAKBANK.NS", "SBIN.NS", "BHARTIARTL.NS",
        "ASIANPAINT.NS", "AXISBANK.NS", "ITC.NS", "BAJFINANCE.NS", "MARUTI.NS",
        "LT.NS", "HCLTECH.NS", "WIPRO.NS", "ULTRACEMCO.NS", "TECHM.NS",
        "SUNPHARMA.NS", "POWERGRID.NS", "TITAN.NS", "NTPC.NS", "TATAMOTORS.NS",
        "GRASIM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS", "ADANIENT.NS",
        "ADANIPORTS.NS", "ONGC.NS", "COALINDIA.NS", "HINDALCO.NS", "UPL.NS",
        "BPCL.NS", "EICHERMOT.NS", "DIVISLAB.NS", "BRITANNIA.NS", "CIPLA.NS",
        "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TATASTEEL.NS", "SBILIFE.NS", "DRREDDY.NS",
        "SHREECEM.NS", "NESTLEIND.NS", "ICICIPRULI.NS", "HDFCLIFE.NS", "M&M.NS"
    ]

    results = []

    for symbol in stock_list:
        data = yf.download(symbol, period="6mo", interval="1d", progress=False)

        if data.empty:
            logger.warning(f"No data returned for {symbol}")
            continue

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        try:
            # Standardize column names early
            data = data.rename(columns={
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Adj Close": "Adj_Close",
                "Volume": "Volume"
            })

            adx_df = calculate_adx(data[['High', 'Low', 'Close']])
            rsi_series = calculate_rsi(data[['Close']])

            if adx_df is not None and isinstance(adx_df, pd.DataFrame):
                adx_df.index = data.index
                data = data.join(adx_df)
            else:
                logger.warning(f"ADX not calculated properly for {symbol}")

            if rsi_series is not None:
                if isinstance(rsi_series, pd.Series):
                    data["RSI"] = rsi_series
                elif isinstance(rsi_series, pd.DataFrame) and "RSI" in rsi_series.columns:
                    data = data.join(rsi_series[["RSI"]])
                else:
                    logger.warning(f"RSI structure unexpected for {symbol}: {type(rsi_series)}")
                    continue

            data = data.dropna(subset=['ADX_14', 'DMP_14', 'DMN_14', 'RSI'])
            if data.empty:
                logger.warning(f"After dropna, no valid rows left for {symbol}")
                continue

            latest = data.iloc[-1]
            latest_date = data.index[-1].strftime("%Y-%m-%d")

            reason = []
            logger.info(f"{symbol} values - ADX: {latest['ADX_14']}, +DI: {latest['DMP_14']}, -DI: {latest['DMN_14']}, RSI: {latest['RSI']}")

            if latest['ADX_14'] <= 30:
                reason.append("ADX <= 30")
            if not (40 < latest['RSI'] < 70):
                reason.append("RSI not in range")
            if latest['DMP_14'] <= latest['DMN_14']:
                reason.append("+DI <= -DI")

            if not reason:
                close_price = latest['Close']
                volume = int(latest['Volume'])
                stop_loss = round(close_price * 0.97, 2)
                results.append({
                    "symbol": symbol,
                    "date": latest_date,
                    "adx": round(latest['ADX_14'], 2),
                    "dmp": round(latest['DMP_14'], 2),
                    "dmn": round(latest['DMN_14'], 2),
                    "rsi": round(latest['RSI'], 2),
                    "volume": volume,
                    "close": round(close_price, 2),
                    "stop_loss": stop_loss
                })
                logger.info(f"Added suggestion: {symbol}")
            else:
                logger.info(f"{symbol} not selected due to: {', '.join(reason)}")

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue

    return results
