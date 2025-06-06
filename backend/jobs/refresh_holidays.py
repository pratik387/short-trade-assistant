import pandas as pd
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import logging

logger = logging.getLogger("nse_holiday_fetcher")

HOLIDAY_FILE = Path(__file__).resolve().parents[2] / "data" / "nse_holidays.csv"
HOLIDAY_URL = "https://www.nseindia.com/products-services/equity-market-timings-holidays"

def download_nse_holidays():
    try:
        logger.info("🌐 Downloading NSE holiday calendar...")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com"
        })
        session.get("https://www.nseindia.com", timeout=5)
        response = session.get(HOLIDAY_URL, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = pd.read_html(str(soup))
        holiday_df = next((df for df in tables if "Date" in df.columns and "Holiday" in df.columns), None)

        if holiday_df is not None:
            holiday_df["Date"] = pd.to_datetime(holiday_df["Date"], errors="coerce")
            holiday_df = holiday_df.dropna(subset=["Date"])
            holiday_df[["Date", "Holiday"]].to_csv(HOLIDAY_FILE, index=False)
            logger.info(f"✅ NSE holidays saved to {HOLIDAY_FILE}")
            return {"status": "success", "count": len(holiday_df)}
        else:
            raise ValueError("Holiday table not found.")

    except Exception as e:
        logger.error(f"❌ Failed to download NSE holidays: {e}")
        return {"status": "failed", "error": str(e)}

if __name__ == "__main__":
    print(download_nse_holidays())
