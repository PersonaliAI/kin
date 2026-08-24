from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)

from plugins import memory as mem

from app.core.clients import genai_client, supabase
from app.core.deps import require_user
from app.schemas.chat import ChatResponse, KinApiMessageRequest

from main import (
    EXECUTIVE_ONLY,
    PAID_PLANS,
    _fmt_tokens,
    _hash_api_key,
    get_monthly_token_usage,
    plan_for,
    quota_state,
    run_assistant,
)

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def web_chat(
    background_tasks: BackgroundTasks,
    text: str = Form(""),
    session_id: str = Form(""),
    audio: Optional[UploadFile] = File(None),
    user: dict[str, Any] = Depends(require_user),
):
    audio_bytes: Optional[bytes] = None
    audio_mime: Optional[str] = None
    if audio is not None:
        audio_bytes = await audio.read()
        audio_mime = audio.content_type or "audio/webm"
    if not text and not audio_bytes:
        raise HTTPException(status_code=400, detail="text or audio required")

    if audio_bytes and plan_for(user) not in PAID_PLANS:
        raise HTTPException(
            status_code=403,
            detail="Voice messages are a Basic+ feature. Upgrade at /dashboard/billing, or just type instead.",
        )

    # Quota gate — block before we spend any model tokens.
    used, limit = quota_state(user)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've used your {_fmt_tokens(limit)} token allowance on the "
                f"{plan_for(user)} plan this month. Upgrade to keep chatting."
            ),
        )

    sid = session_id or f"web-{user['id']}"
    try:
        result = await run_assistant(
            user=user,
            text=text,
            audio_bytes=audio_bytes,
            audio_mime=audio_mime,
            source="web",
            session_id=sid,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"assistant failed: {exc}") from exc

    reply = result["reply"]
    thinking = result.get("thinking") or None

    # Extract & store memories in the background — doesn't block the reply.
    if text:
        background_tasks.add_task(
            mem.extract_and_store,
            supabase,
            genai_client,
            user=user,
            user_msg=text,
            assistant_reply=reply,
            session_id=sid,
        )

    return ChatResponse(reply=reply, session_id=sid, thinking=thinking)


@router.get("/api/usage")
async def usage(user: dict[str, Any] = Depends(require_user)):
    used, limit = quota_state(user)
    plan = plan_for(user)
    now = datetime.now(tz=timezone.utc)
    # Next reset: first of next month UTC.
    if now.month == 12:
        reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "plan": plan,
        "unit": "tokens",
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "resets_at": reset.isoformat(),
        "tokens": get_monthly_token_usage(user["id"]),
    }


def _resolve_kin_api_key(authorization: Optional[str]) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer API key")
    raw = authorization.split(" ", 1)[1].strip()
    res = supabase.table("kin_api_keys").select("*").eq("key_hash", _hash_api_key(raw)).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="Invalid API key")
    key_row = res.data[0]
    if key_row.get("revoked"):
        raise HTTPException(status_code=401, detail="API key revoked")
    return key_row


@router.post("/api/v1/messages")
async def kin_public_api_message(
    body: KinApiMessageRequest,
    authorization: Optional[str] = Header(None),
):
    """Programmatic access to a user's own Kin, authenticated with a Kin API
    key instead of a Supabase session — the "custom API" advertised on
    Executive. Counts against the same monthly message quota as the web/
    web chat, since it runs the exact same model calls."""
    key_row = _resolve_kin_api_key(authorization)
    user_res = supabase.table("users").select("*").eq("id", key_row["user_id"]).execute()
    if not user_res.data:
        raise HTTPException(status_code=401, detail="API key owner not found")
    user = user_res.data[0]
    if plan_for(user) not in EXECUTIVE_ONLY:
        # Plan may have lapsed since the key was issued.
        raise HTTPException(status_code=403, detail="API access requires an active Executive plan")

    used, limit = quota_state(user)
    if used >= limit:
        raise HTTPException(
            status_code=429, detail=f"Monthly token quota of {_fmt_tokens(limit)} reached"
        )

    supabase.table("kin_api_keys").update({
        "last_used_at": datetime.now(timezone.utc).isoformat(),
        "request_count": (key_row.get("request_count") or 0) + 1,
    }).eq("id", key_row["id"]).execute()

    sid = body.session_id or f"api-{user['id']}"
    result = await run_assistant(
        user=user, text=body.text, audio_bytes=None, audio_mime=None,
        source="api", session_id=sid,
    )
    return {"reply": result["reply"], "session_id": sid}


@router.get("/api/chat/sessions")
async def chat_sessions_list(user: dict[str, Any] = Depends(require_user)):
    """List the user's web chat sessions, newest first, with a preview."""
    # Pull all web messages and group by session_id. Cheaper than RPC for our scale.
    res = (
        supabase.table("messages")
        .select("session_id, role, content, created_at")
        .eq("user_id", user["id"])
        .eq("source", "web")
        .order("created_at", desc=False)
        .limit(2000)
        .execute()
    )
    by_session: dict[str, dict[str, Any]] = {}
    for row in res.data or []:
        sid = row.get("session_id") or ""
        if not sid:
            continue
        s = by_session.setdefault(
            sid,
            {
                "session_id": sid,
                "title": None,
                "message_count": 0,
                "first_at": row["created_at"],
                "last_at": row["created_at"],
            },
        )
        s["message_count"] += 1
        s["last_at"] = row["created_at"]
        if s["title"] is None and row.get("role") == "user" and row.get("content"):
            s["title"] = (row["content"] or "").strip()[:80]
    sessions = sorted(
        by_session.values(), key=lambda s: s["last_at"], reverse=True
    )
    return {"sessions": sessions}


@router.delete("/api/chat/sessions/{session_id}")
async def chat_session_delete(
    session_id: str, user: dict[str, Any] = Depends(require_user)
):
    # To prevent users from resetting/refunding their monthly token usage quota
    # by deleting chat sessions (which would allow unlimited API usage abuse),
    # we perform a privacy-preserving soft-delete. We wipe the actual message
    # content, audio, and tools metadata (respecting GDPR/privacy), but keep
    # the message records with their token counts intact for quota tracking.
    supabase.table("messages").update({
        "content": "[deleted]",
        "audio_url": None,
        "tool_calls": None,
        "session_id": f"deleted-{session_id}-{int(time.time())}",
    }).eq("user_id", user["id"]).eq("source", "web").eq("session_id", session_id).execute()
    return {"status": "deleted", "session_id": session_id}
