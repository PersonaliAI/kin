from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.core import security as _sec
from app.core.clients import supabase
from app.core.deps import require_user

from main import plan_for

logger = logging.getLogger("kin")

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Returns server status. Used by Cloud Run health probes.",
    response_description="Server is healthy",
)
async def health_check(request: Request):
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": _sec.get_request_id(request),
    }


@router.get("/api/capabilities")
async def get_capabilities(user: dict[str, Any] = Depends(require_user)):
    """Report which optional integrations are configured on the backend so the
    UI can gate provider choices."""
    # FIX: this was `import notifications as _notify` — a bare top-level
    # import that only works if `plugins/` itself is on sys.path, which it
    # isn't at app startup (only scripts/graph_parity_check.py adds it, for
    # its own standalone CLI use — see that file). Every other call site in
    # this codebase (main.py, plugins/agent_tools.py) uses the form below,
    # which is what actually resolves given this app's real import context.
    # The bug made every call to GET /api/capabilities raise
    # ModuleNotFoundError: No module named 'notifications'.
    from plugins import notifications as _notify
    return {
        "onesignal_configured": _notify.onesignal_configured(),
    }


@router.get("/api/export")
async def export_my_data(user: dict[str, Any] = Depends(require_user)):
    """Everything Kin has on this user, as a single downloadable JSON file —
    full chat history and long-term memories. Deliberately excludes OAuth
    tokens, password/auth internals, and other users' data."""
    messages = (
        supabase.table("messages")
        .select("role, content, source, session_id, created_at")
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    ).data or []
    memories = (
        supabase.table("memory_embeddings")
        .select("content, kind, created_at")
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    ).data or []
    scheduled_tasks = (
        supabase.table("scheduled_tasks")
        .select("name, prompt, cron_expression, timezone, channel, is_active, created_at")
        .eq("user_id", user["id"])
        .execute()
    ).data or []
    profile = {
        "display_name": user.get("display_name"),
        "timezone": user.get("timezone"),
        "country": user.get("country"),
        "plan": plan_for(user),
        "google_email": user.get("google_email"),
        "microsoft_email": user.get("microsoft_email"),
    }
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "messages": messages,
        "memories": memories,
        "scheduled_tasks": scheduled_tasks,
    }
    filename = f"kin-export-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    return Response(
        content=json.dumps(export, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
