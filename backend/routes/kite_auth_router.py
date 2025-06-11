from fastapi import Request, APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from brokers.kite.kite_client import kite, KITE_API_SECRET, TOKEN_FILE, KITE_REDIRECT_URI, KITE_API_KEY
from exceptions.exceptions import KiteException
import os
import logging
from pathlib import Path

# Configure logger once (e.g. in your main app)
logger = logging.getLogger("kite_auth")
logger.setLevel(logging.INFO)

# Fallback frontend URL
FRONTEND_URL = os.getenv("FRONTEND_URL")

kite_router = APIRouter()

@kite_router.get("/kite-callback")
async def kite_callback_handler(request: Request):
    token = request.query_params.get("request_token")
    status = request.query_params.get("status")

    if status != "success" or not token:
        logger.warning("Kite login failed or missing request_token; status=%s token=%r", status, token)
        return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=failed")

    # 1) Exchange code for session
    try:
        data = kite.generate_session(token, api_secret=KITE_API_SECRET)
        access_token = data["access_token"]
    except KiteException as e:
        logger.exception("Failed to generate Kite session")
        return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=failed")
    except Exception:
        logger.exception("Unexpected error generating Kite session")
        return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=failed")

    # 2) Persist the token safely
    try:
        token_path = Path(TOKEN_FILE)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(access_token)
    except OSError as e:
        logger.exception("Failed to write access token to disk")
        # consider a JSON error instead of redirect?
        return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=failed")

    # 3) Tell the Kite client to use it
    try:
        kite.set_access_token(access_token)
    except KiteException:
        logger.exception("Failed to set access_token on Kite client")
        # token is already on disk, but client may be misconfigured
        return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=failed")

    logger.info("Kite login succeeded; access token stored")
    return RedirectResponse(f"{FRONTEND_URL}/kite-callback?kite_login=success")


@kite_router.get("/api/kite/session-status")
async def check_kite_session():
    try:
        kite.profile()  # this raises if not authenticated
        return {"logged_in": True}
    except KiteException:
        logger.debug("Kite session invalid or expired")
        return {"logged_in": False}
    except Exception:
        logger.exception("Unexpected error checking Kite session")
        raise HTTPException(status_code=500, detail="Internal error checking session")


@kite_router.get("/api/kite/login-url")
async def get_login_url():
    url = (
        "https://kite.zerodha.com/connect/login?"
        f"api_key={KITE_API_KEY}&v=3&redirect_uri={KITE_REDIRECT_URI}"
    )
    return {"url": url}
