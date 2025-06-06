import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Logger
logger = logging.getLogger("kite_client")

# Credentials and token path
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
TOKEN_FILE = Path(__file__).resolve().parents[2] / "kite_token.txt"


# Kite instance
kite = KiteConnect(api_key=KITE_API_KEY)

# ---- Session Management ----

def set_access_token_from_file():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            kite.set_access_token(token)
            logger.info("Access token loaded from file")
    else:
        logger.warning("Access token file not found")

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
            logger.info(f"Token revalidated for user: {profile['user_name']}")
            return True
        except Exception as e2:
            logger.error(f"Access token invalid after retry: {e2}. Please login via Zerodha.")
            return False

# ---- Client Wrapper ----

class KiteClient:
    def __init__(self):
        set_access_token_from_file()
        if not validate_access_token():
            logger.error("Invalid or expired Kite token.")
            raise RuntimeError("Kite session invalid")

    def ensure_session(self):
        if not validate_access_token():
            raise RuntimeError("Kite session not valid. Please login again.")

# Optional getter

def get_kite() -> KiteConnect:
    if not validate_access_token():
        raise RuntimeError("Kite session invalid")
    return kite
