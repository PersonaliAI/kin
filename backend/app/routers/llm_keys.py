from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.clients import supabase
from app.core.deps import require_user
from app.core.llm_catalog import BYOK_PROVIDERS, MODEL_CATALOG
from app.schemas.llm_keys import LlmKeySave

from main import _credentials_fernet

logger = logging.getLogger("kin")

router = APIRouter()

_SLUG_PREFIX = "llm:"


@router.get("/api/llm-models")
async def list_llm_models(user: dict[str, Any] = Depends(require_user)):
    """Static provider/model catalog for the frontend's model selector, with
    per-user `has_key` computed from user_credentials in a single query."""
    res = (
        supabase.table("user_credentials")
        .select("integration_slug")
        .eq("user_id", user["id"])
        .like("integration_slug", f"{_SLUG_PREFIX}%")
        .execute()
    )
    keyed_providers = {
        row["integration_slug"][len(_SLUG_PREFIX):] for row in (res.data or [])
    }

    providers = []
    for entry in MODEL_CATALOG:
        provider_id = entry["id"]
        has_key = True if provider_id not in BYOK_PROVIDERS else provider_id in keyed_providers
        providers.append({**entry, "has_key": has_key})

    return {"providers": providers}


@router.get("/api/llm-keys")
async def list_llm_keys(user: dict[str, Any] = Depends(require_user)):
    """Which BYOK providers the user has a saved key for. Never returns the
    key itself (not even masked) — just presence + when it was last saved."""
    try:
        res = (
            supabase.table("user_credentials")
            .select("integration_slug, updated_at")
            .eq("user_id", user["id"])
            .like("integration_slug", f"{_SLUG_PREFIX}%")
            .execute()
        )
        keys = [
            {"provider": row["integration_slug"][len(_SLUG_PREFIX):], "updated_at": row["updated_at"]}
            for row in (res.data or [])
        ]
        return {"keys": keys}
    except Exception as e:
        logger.exception("Failed to list llm keys")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/llm-keys")
async def save_llm_key(body: LlmKeySave, user: dict[str, Any] = Depends(require_user)):
    if body.provider not in BYOK_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"'{body.provider}' is not a BYOK provider. Must be one of: {', '.join(sorted(BYOK_PROVIDERS))}.",
        )
    if not body.api_key or not body.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key is required")

    try:
        ciphertext = _credentials_fernet().encrypt(body.api_key.strip().encode())
        supabase.table("user_credentials").upsert({
            "user_id": user["id"],
            "integration_slug": f"{_SLUG_PREFIX}{body.provider}",
            "auth_type": "api_key",
            "encrypted_payload": f"\\x{ciphertext.hex()}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to save llm key")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/llm-keys/{provider}")
async def delete_llm_key(provider: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("user_credentials").delete().eq("user_id", user["id"]).eq(
            "integration_slug", f"{_SLUG_PREFIX}{provider}"
        ).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to delete llm key")
        raise HTTPException(status_code=500, detail=str(e))
