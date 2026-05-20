import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]

# Lemon Squeezy
LS_API_KEY = os.environ["LS_API_KEY"]
LS_WEBHOOK_SECRET = os.environ["LS_WEBHOOK_SECRET"]
LS_STORE_ID = os.environ["LS_STORE_ID"]
LS_VARIANTS = {
    "starter": os.environ.get("LS_VARIANT_STARTER", ""),
    "pro": os.environ.get("LS_VARIANT_PRO", ""),
    "expert": os.environ.get("LS_VARIANT_EXPERT", ""),
}

JWT_SECRET = os.environ["JWT_SECRET"]
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")

PLAN_LIMITS = {
    "starter": {"secteurs": 1, "alertes_immediates": False},
    "pro": {"secteurs": 3, "alertes_immediates": True},
    "expert": {"secteurs": 99, "alertes_immediates": True},
}
