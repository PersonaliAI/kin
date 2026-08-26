"""Shared client singletons — Supabase and the Gemini (genai) client."""

from __future__ import annotations

from google import genai
from supabase import Client, create_client

from app.core.config import (
    GEMINI_API_KEY,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)


# KNOWN ARCHITECTURAL RISK (flagged by security audit, deliberately NOT
# fixed in that pass — see below): this single client, built with the
# service-role key, is imported and used for essentially every database
# call across the entire app (all routers, all plugins). The service role
# bypasses Row Level Security entirely, which means the RLS policies
# defined throughout supabase/migrations/ (e.g. 20260818020000_rls_lockdown.sql)
# provide NO actual defense-in-depth here — they never run. Tenant
# isolation for the whole application depends entirely on every single
# query handler remembering to add the right `.eq("user_id", ...)` /
# `.eq("id", ...)` filter by hand, with no second layer to catch a mistake.
# One missed filter anywhere is a direct cross-tenant IDOR.
#
# This was NOT fixed here because a real fix (e.g. switching user-scoped
# reads/writes to a per-request client authenticated with the user's own
# Supabase session JWT, so RLS actually enforces tenant isolation) means
# touching the ~120+ call sites across this codebase that currently assume
# an un-scoped service-role client, and getting that wrong is itself a
# security risk. That's a dedicated follow-up project, not a drive-by
# change — flagged for the team rather than guessed at.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# GEMINI_API_KEY (Google AI Studio, free tier) is a separate billing surface
# from Vertex AI — set it to route all Gemini calls through AI Studio instead
# (e.g. when the GCP project's Vertex AI billing is blocked/suspended).
# Vertex AI stays as the default/fallback path when GEMINI_API_KEY is unset,
# unchanged from before.
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    genai_client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        # gemini-3.x models are only served from the "global" Vertex AI endpoint,
        # not region-pinned ones like us-central1 (confirmed empirically — they
        # 404 there). "global" also works fine for the older 2.5 models and
        # text-embedding-004 that OCR/memory still use, so one client covers all.
        location=GOOGLE_CLOUD_LOCATION,
    )
