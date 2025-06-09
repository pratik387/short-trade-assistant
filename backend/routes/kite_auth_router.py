from fastapi import Request, APIRouter
from fastapi.responses import RedirectResponse
from brokers.kite.kite_client import kite, KITE_API_SECRET, TOKEN_FILE, KITE_REDIRECT_URI , KITE_API_KEY
import os
import logging

logger = logging.getLogger("kite_auth")
kite_router = APIRouter()

@kite_router.get("/kite-callback")
def kite_callback_handler(request: Request):
    token = request.query_params.get("request_token")
    status = request.query_params.get("status")

    if status != "success" or not token:
        logger.warning("❌ Kite login failed or missing request_token")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/kite-callback?kite_login=failed")

    try:
        data = kite.generate_session(token, api_secret=KITE_API_SECRET)
        access_token = data["access_token"]

        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)
        kite.set_access_token(access_token)

        logger.info("✅ Access token generated and stored successfully")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/kite-callback?kite_login=success")

    except Exception as e:
        logger.error(f"❌ Failed to generate session: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/kite-callback?kite_login=failed")


@kite_router.get("/api/kite/session-status")
def check_kite_session():
    try:
        kite.profile()
        return {"logged_in": True}
    except:
        return {"logged_in": False}
    
@kite_router.get("/api/kite/login-url")
def get_login_url():
    login_url = (
        f"https://kite.zerodha.com/connect/login?"
        f"api_key={KITE_API_KEY}"
        f"&v=3"
        f"&redirect_uri={KITE_REDIRECT_URI}"
    )
    return {"url": login_url}
