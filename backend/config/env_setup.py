# @role: Environment loader for backend settings
# @used_by: kite_client.py, tick_listener.py

# @filter_type: utility
# @tags: env, config, bootstrap
# config/env.py

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Determine project root & ENV ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
ENV  = os.getenv("ENV", "development").lower()

# ─── Load the right .env file ────────────────────────────────────────────────
env_path = ROOT / f".env.{ENV}"
if not env_path.exists():
    raise FileNotFoundError(f"Missing environment file: {env_path.name}")
load_dotenv(env_path)

# ─── Expose your environment settings ────────────────────────────────────────
class EnvConfig:
    ENV                = ENV
    GMAIL_USER         = os.getenv("GMAIL_USER")
    GMAIL_PASS         = os.getenv("GMAIL_PASS")
    ALERT_TO           = os.getenv("ALERT_TO")
    KITE_REDIRECT_URI  = os.getenv("KITE_REDIRECT_URI")
    KITE_API_KEY       = os.getenv("KITE_API_KEY")
    KITE_API_SECRET    = os.getenv("KITE_API_SECRET")
    KITE_REQUEST_TOKEN = os.getenv("KITE_REQUEST_TOKEN")
    TWILIO_SID         = os.getenv("TWILIO_SID")
    TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE       = os.getenv("TWILIO_PHONE")
    YOUR_PHONE         = os.getenv("YOUR_PHONE")
    FRONTEND_URL       = os.getenv("FRONTEND_URL")
    TRADE_MODE         = os.getenv("TRADE_MODE", "mock").lower()
    OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")

env = EnvConfig()