from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.clients import supabase
from app.core.deps import require_user
from app.schemas.settings import FlowCredentialsSave, KinApiKeyCreate, SettingsPatch

from main import PAID_PLANS, PRO_PLUS_PLANS, _credentials_fernet, _hash_api_key, _require_executive, plan_for

logger = logging.getLogger("kin")

router = APIRouter()


# ---- Custom API ---------------------------------------------------------

_KIN_API_KEY_PREFIX = "kin_sk_"


@router.post("/api/kin/api-keys")
async def create_kin_api_key(body: KinApiKeyCreate, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    raw = _KIN_API_KEY_PREFIX + secrets.token_hex(24)
    row = supabase.table("kin_api_keys").insert({
        "user_id": user["id"],
        "name": body.name or "API key",
        "key_hash": _hash_api_key(raw),
        "key_prefix": raw[: len(_KIN_API_KEY_PREFIX) + 6],
    }).execute()
    return {**row.data[0], "key": raw}  # raw key only ever returned on creation


@router.get("/api/kin/api-keys")
async def list_kin_api_keys(user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    res = (
        supabase.table("kin_api_keys")
        .select("id, name, key_prefix, revoked, request_count, last_used_at, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return {"api_keys": res.data or []}


@router.delete("/api/kin/api-keys/{key_id}")
async def revoke_kin_api_key(key_id: str, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    supabase.table("kin_api_keys").update({"revoked": True}).eq("id", key_id).eq("user_id", user["id"]).execute()
    return {"status": "revoked"}


@router.patch("/api/settings")
async def update_settings(patch: SettingsPatch, user: dict[str, Any] = Depends(require_user)):
    plan = plan_for(user)
    # Treat empty string as "clear the value" for nullable text fields.
    raw = patch.dict(exclude_unset=True)
    payload: dict[str, Any] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if k == "country" and v == "":
            payload[k] = None
        elif k == "email_signature_links":
            # patch.dict() already serialized nested SignatureLink models to
            # plain dicts, so `v` is a list[dict] here — just cap the count.
            payload[k] = v[:5]
        else:
            payload[k] = v

    if "system_prompt" in payload and payload["system_prompt"] and plan not in PRO_PLUS_PLANS:
        raise HTTPException(
            status_code=403,
            detail="Custom system prompt is a Pro feature. Upgrade at /dashboard/billing to set one.",
        )
    if payload.get("briefing_enabled") is True and plan not in PAID_PLANS:
        raise HTTPException(
            status_code=403,
            detail="The daily morning briefing is a Basic+ feature. Upgrade at /dashboard/billing to enable it.",
        )
    if payload.get("email_followups_enabled") is True and plan not in PAID_PLANS:
        raise HTTPException(
            status_code=403,
            detail="Email follow-ups are a Basic+ feature. Upgrade at /dashboard/billing to enable them.",
        )

    if not payload:
        return {"status": "noop"}
    supabase.table("users").update(payload).eq("id", user["id"]).execute()
    return {"status": "ok"}


@router.get("/api/flow-credentials")
async def get_flow_credentials(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("user_credentials").select("integration_slug, auth_type, expires_at, updated_at").eq("user_id", user["id"]).execute()
        return {"credentials": res.data or []}
    except Exception as e:
        logger.exception("Failed to fetch flow credentials")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/flow-credentials")
async def save_flow_credentials(body: FlowCredentialsSave, user: dict[str, Any] = Depends(require_user)):
    try:
        # Encrypt the JSON payload
        plaintext = json.dumps(body.payload).encode()
        ciphertext = _credentials_fernet().encrypt(plaintext)

        # Determine authentication type (e.g. oauth, api_key) based on payload contents
        auth_type = "api_key"
        if "access_token" in body.payload or "refresh_token" in body.payload:
            auth_type = "oauth"
        elif not body.payload:
            auth_type = "none"

        supabase.table("user_credentials").upsert({
            "user_id": user["id"],
            "integration_slug": body.integration_slug,
            "auth_type": auth_type,
            "encrypted_payload": f"\\x{ciphertext.hex()}",  # Hex string format for Postgres BYTEA
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        return {"status": "success"}
    except Exception as e:
        logger.exception("Failed to save flow credentials")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/flow-credentials/{slug}")
async def delete_flow_credentials(slug: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("user_credentials").delete().eq("user_id", user["id"]).eq("integration_slug", slug).execute()
        return {"status": "success"}
    except Exception as e:
        logger.exception("Failed to delete flow credentials")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/flow-limits")
async def get_flow_limits(user: dict[str, Any] = Depends(require_user)):
    try:
        plan = user.get("plan", "free")
        max_flows = 100 if plan == "premium" else 10
        max_runs = 10000 if plan == "premium" else 1000

        # Query current active flows
        flows_res = supabase.table("flows").select("id", count="exact").eq("user_id", user["id"]).eq("status", "active").execute()
        active_flows = flows_res.count or 0

        return {
            "plan": plan,
            "limits": {"max_flows": max_flows, "max_runs_per_month": max_runs, "can_publish": 1},
            "usage": {"active_flows": active_flows, "runs_this_month": 0}
        }
    except Exception as e:
        logger.exception("Failed to fetch flow limits")
        raise HTTPException(status_code=500, detail=str(e))
