from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.clients import supabase
from app.core.deps import require_user
from app.schemas.kin_webhooks import KinWebhookCreate, KinWebhookPatch

from main import _require_executive

router = APIRouter()

# ---- Webhooks ---------------------------------------------------------------

KIN_WEBHOOK_EVENTS = {"message.created"}


@router.post("/api/kin/webhooks")
async def create_kin_webhook(body: KinWebhookCreate, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    if not body.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must be https://")
    events = [e for e in body.events if e in KIN_WEBHOOK_EVENTS] or ["message.created"]
    secret = "whsec_" + secrets.token_hex(24)
    row = supabase.table("kin_webhooks").insert({
        "user_id": user["id"], "url": body.url, "events": events, "secret": secret,
    }).execute()
    created = row.data[0]
    return {**created, "secret": secret}  # secret only ever returned on creation


@router.get("/api/kin/webhooks")
async def list_kin_webhooks(user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    res = (
        supabase.table("kin_webhooks")
        .select("id, url, events, active, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return {"webhooks": res.data or []}


@router.patch("/api/kin/webhooks/{webhook_id}")
async def update_kin_webhook(
    webhook_id: str, body: KinWebhookPatch, user: dict[str, Any] = Depends(require_user)
):
    _require_executive(user)
    owned = supabase.table("kin_webhooks").select("id").eq("id", webhook_id).eq("user_id", user["id"]).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Webhook not found")
    patch = body.dict(exclude_unset=True)
    if patch:
        supabase.table("kin_webhooks").update(patch).eq("id", webhook_id).execute()
    return {"status": "ok"}


@router.delete("/api/kin/webhooks/{webhook_id}")
async def delete_kin_webhook(webhook_id: str, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    supabase.table("kin_webhooks").delete().eq("id", webhook_id).eq("user_id", user["id"]).execute()
    return {"status": "deleted"}


@router.get("/api/kin/webhooks/{webhook_id}/deliveries")
async def list_kin_webhook_deliveries(webhook_id: str, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    owned = supabase.table("kin_webhooks").select("id").eq("id", webhook_id).eq("user_id", user["id"]).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Webhook not found")
    res = (
        supabase.table("kin_webhook_deliveries")
        .select("id, event, status, response_code, last_error, created_at, delivered_at")
        .eq("webhook_id", webhook_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return {"deliveries": res.data or []}
