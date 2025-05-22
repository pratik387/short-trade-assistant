from fastapi import Request, APIRouter
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv
from pathlib import Path
import logging

# Load .env from the backend folder
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# Setup logger
logger = logging.getLogger("kite_auth")

# Load credentials
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
TOKEN_FILE = Path(__file__).resolve().parents[1] / "kite_token.txt"

# Initialize Kite
kite = KiteConnect(api_key=KITE_API_KEY)
kite_router = APIRouter()

@kite_router.get("/kite-login-url")
def kite_login_url_handler():
    login_url = kite.login_url()
    logger.info(f"Generated login URL: {login_url}")
    return {"login_url": login_url}

@kite_router.get("/kite-callback")
def kite_callback_handler(request: Request):
    token = request.query_params.get("request_token")
    if token:
        try:
            data = kite.generate_session(token, api_secret=KITE_API_SECRET)
            access_token = data["access_token"]

            # Save access token to file
            with open(TOKEN_FILE, "w") as f:
                f.write(access_token)

            # Set for current kite instance
            kite.set_access_token(access_token)
            logger.info("✅ Access token generated and stored successfully")
            return {"status": "success", "access_token": access_token}
        except Exception as e:
            logger.error(f"❌ Failed to generate session: {e}")
            return {"status": "failed", "reason": str(e)}

    logger.warning("Missing request_token in callback")
    return {"status": "failed", "reason": "Missing request_token"}
