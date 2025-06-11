import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from kiteconnect import KiteConnect
from exceptions.exceptions import InvalidTokenException

# Load environment
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Logger setup
logger = logging.getLogger("kite_client")

# Env credentials
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
KITE_REDIRECT_URI = os.getenv("KITE_REDIRECT_URI")

# Token file
TOKEN_FILE = Path(__file__).resolve().parents[2] / "kite_token.txt"

# Kite instance
kite = KiteConnect(api_key=KITE_API_KEY)

def set_access_token_from_file():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            kite.set_access_token(token)
            logger.info("🔑 Access token loaded from file.")
    else:
        logger.warning("⚠️ Access token file not found.")

def validate_access_token(raise_on_failure=True) -> bool:
    try:
        profile = kite.profile()
        logger.info(f"✅ Valid Kite session for user: {profile['user_name']}")
        return True
    except Exception as e:
        logger.warning(f"❌ Initial token validation failed: {e}")
        set_access_token_from_file()
        try:
            profile = kite.profile()
            logger.info(f"🔁 Token revalidated for user: {profile['user_name']}")
            return True
        except Exception as e2:
            logger.error(f"❌ Token invalid after retry: {e2}")
            if raise_on_failure:
                raise InvalidTokenException("Kite token invalid. Login required.")
            return False

def get_kite() -> KiteConnect:
    """
    Returns a session-validated kite client. Raises InvalidTokenException if session is broken.
    """
    if validate_access_token(raise_on_failure=True):
        return kite
    raise InvalidTokenException("Unable to get valid Kite session.")

class KiteClient:
    def __init__(self):
        set_access_token_from_file()
        if not validate_access_token():
            raise InvalidTokenException("Kite token is invalid or expired.")

    def ensure_session(self):
        if not validate_access_token():
            raise InvalidTokenException("Kite session not valid. Please login again.")
