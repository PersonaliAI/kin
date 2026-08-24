"""Environment-derived configuration constants, shared across the app."""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Self-loading: must happen before any os.environ.get() below, and before
# any other module reads env vars — since this is the first thing anything
# in app.core imports, loading .env here (rather than relying on main.py to
# call it first) guarantees correct env state regardless of import order.
load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# Primary model. Override with KIN_MODEL or (legacy) GEMMA_MODEL env vars.
#
# 2026-07-21: briefly tried gemini-2.5-flash-lite as primary for its ~15-22x
# lower cost, reverted the same day — confirmed in production, not just
# theorized: with a job-application request (a just-shared photo + resume,
# "need to apply this job"), the lite model repeatedly refused to call
# read_full_document and instead hallucinated "I can't access images" even
# after the resume/photo were successfully indexed and the existing
# no-tool-call refusal-detector forced a retry. flash (not flash-lite) is
# the brain; we only fall back to the lite model when flash is rate-limited.
MODEL_NAME = (
    os.environ.get("KIN_MODEL")
    or os.environ.get("GEMMA_MODEL")
    or "gemini-2.5-flash-lite"
)

FUNCTION_SECRET = os.environ.get("FUNCTION_SECRET", "")
# Lemon Squeezy — accept either naming convention.
LEMON_WEBHOOK_SECRET = (
    os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET")
    or os.environ.get("LEMON_SQUEEZY_WEBHOOK_SECRET", "")
)
LEMON_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY", "")
LEMON_STORE_ID = os.environ.get("LEMONSQUEEZY_STORE_ID", "")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://personaliai.com")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://personaliai.com,https://chatty.personaliai.com,http://localhost:3000",
    ).split(",")
    if o.strip()
]

# Lemon Squeezy variant_id → plan name. Prefer dedicated env vars, then fall back
# to a comma-separated LEMON_VARIANT_PLANS list.
LEMON_VARIANT_TO_PLAN: dict[str, str] = {}
for _env_key, _plan in (
    ("LEMONSQUEEZY_VARIANT_BASIC", "basic"),
    ("LEMONSQUEEZY_VARIANT_PRO", "pro"),
    ("LEMONSQUEEZY_VARIANT_EXECUTIVE", "executive"),
):
    _val = os.environ.get(_env_key)
    if _val:
        LEMON_VARIANT_TO_PLAN[_val.strip()] = _plan
for _v in os.environ.get("LEMON_VARIANT_PLANS", "").split(","):
    if ":" in _v:
        _k, _p = _v.strip().split(":", 1)
        LEMON_VARIANT_TO_PLAN[_k] = _p

# GEMINI_API_KEY (Google AI Studio, free tier) is a separate billing surface
# from Vertex AI — set it to route all Gemini calls through AI Studio instead
# (e.g. when the GCP project's Vertex AI billing is blocked/suspended).
# Vertex AI stays as the default/fallback path when GEMINI_API_KEY is unset,
# unchanged from before.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

# No-op when SENTRY_DSN is unset, so local/dev runs need no Sentry account.
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
SENTRY_ENV = os.environ.get("SENTRY_ENV", "production")
SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
