from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)

from plugins import memory as mem

from app.core import llm as core_llm
from app.core import security as _sec
from app.core.clients import genai_client, supabase
from app.core.deps import require_user
from app.core.llm_catalog import BYOK_PROVIDERS, DEFAULT_MODELS
from app.schemas.chat import ChatResponse, KinApiMessageRequest

from main import (
    PAID_PLANS,
    _credentials_fernet,
    _fmt_tokens,
    _hash_api_key,
    _load_history,
    _month_start_iso,
    _persist,
    _system_prompt_for,
    get_monthly_token_usage,
    plan_for,
    quota_state,
    run_assistant,
)

router = APIRouter()

_BYOK_SLUG_PREFIX = "llm:"


async def _byok_chat_reply(
    *, user: dict[str, Any], provider: str, preferred_model: Optional[str], text: str, session_id: str,
) -> str:
    """Plain-text completion via a customer-supplied key, bypassing
    run_assistant's Gemini-only tool-calling loop entirely.

    Known limitation: no tool-calling (lead capture, calendar, Gmail,
    memory-write tools, etc.) on this path — BYOK providers' function-call
    schemas differ enough from Gemini's that wiring them in is a separate,
    larger effort (see plugins/llm_providers.py's module docstring). RAG
    (semantic memory retrieval) and rolling-history-summary injection are
    reused as-is from main.py's _system_prompt_for/mem.retrieve, so the
    BYOK reply is still knowledge-base-grounded, just without tools.
    """
    key_res = (
        supabase.table("user_credentials")
        .select("encrypted_payload")
        .eq("user_id", user["id"])
        .eq("integration_slug", f"{_BYOK_SLUG_PREFIX}{provider}")
        .execute()
    )
    if not key_res.data:
        raise HTTPException(
            status_code=400,
            detail=f"No API key saved for {provider}. Add one in Settings, or switch back to Gemini.",
        )
    raw_payload = key_res.data[0]["encrypted_payload"]
    # Supabase returns bytea as a hex string prefixed with "\x" (postgres
    # hex-encoded bytea representation) — same convention save_flow_credentials
    # writes it in.
    if isinstance(raw_payload, str):
        hex_str = raw_payload[2:] if raw_payload.startswith("\\x") else raw_payload
        ciphertext = bytes.fromhex(hex_str)
    else:
        ciphertext = bytes(raw_payload)
    try:
        api_key = _credentials_fernet().decrypt(ciphertext).decode()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Stored API key for {provider} could not be decrypted. Please re-save it in Settings.",
        ) from exc

    memory_snippet = ""
    if user.get("memory_enabled", True) and text and len(text.strip()) >= 8:
        try:
            mems = mem.retrieve(supabase, genai_client, user_id=user["id"], query=text)
            memory_snippet = mem.format_for_prompt(mems)
        except Exception:  # noqa: BLE001 — never let memory retrieval break the turn
            pass

    system_prompt = _system_prompt_for(user, memory_snippet=memory_snippet)

    history = _load_history(user["id"], "web", session_id)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for row in history[:-1]:  # exclude the just-persisted current user message
        raw = (row.get("content") or "").strip()
        if not raw or raw == "[voice message]":
            continue
        messages.append({"role": "user" if row["role"] == "user" else "assistant", "content": raw})
    messages.append({"role": "user", "content": text})

    model = preferred_model or DEFAULT_MODELS.get(provider, "")
    result = await core_llm.complete(
        model=f"{provider}/{model}",
        messages=messages,
        max_tokens=2048,
        api_key=api_key,
        feature="chat_byok",
        user_id=user["id"],
    )
    return result.text


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

    pref_res = (
        supabase.table("users")
        .select("preferred_provider, preferred_model")
        .eq("id", user["id"])
        .single()
        .execute()
    )
    preferred_provider = (pref_res.data or {}).get("preferred_provider") or "gemini"
    preferred_model = (pref_res.data or {}).get("preferred_model")

    thinking: Optional[str] = None
    if preferred_provider in BYOK_PROVIDERS:
        if audio_bytes:
            raise HTTPException(
                status_code=400,
                detail="Voice messages aren't supported with a BYOK provider yet — switch to Gemini to send audio.",
            )
        started = time.monotonic()
        _persist(user_id=user["id"], role="user", content=text, source="web", session_id=sid)
        try:
            reply = await _byok_chat_reply(
                user=user, provider=preferred_provider, preferred_model=preferred_model,
                text=text, session_id=sid,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"assistant failed: {exc}") from exc
        _persist(
            user_id=user["id"], role="assistant", content=reply, source="web", session_id=sid,
            latency_ms=int((time.monotonic() - started) * 1000),
            model=f"{preferred_provider}/{preferred_model or DEFAULT_MODELS.get(preferred_provider, '')}",
        )
    else:
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
    # Fetched once and reused for quota_state() below — this endpoint used
    # to call get_monthly_token_usage() twice (once inside quota_state(),
    # once directly for the "tokens" field), each doing a real DB round
    # trip. See migration 20260831010000's comment for the full story.
    token_usage = get_monthly_token_usage(user["id"])
    used, limit = quota_state(user, token_usage)
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
        "tokens": token_usage,
    }


def _aggregate_llm_calls(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_cost = 0.0
    total_tokens = 0
    unknown_cost_calls = 0
    by_model: dict[tuple[str, str], dict[str, Any]] = {}
    by_feature: dict[str, dict[str, Any]] = {}

    for row in rows:
        tokens = row.get("total_tokens") or 0
        cost = row.get("cost_usd")
        total_tokens += tokens
        if cost is None:
            unknown_cost_calls += 1
        else:
            total_cost += cost

        model_key = (row.get("provider") or "unknown", row.get("model") or "unknown")
        m = by_model.setdefault(model_key, {"provider": model_key[0], "model": model_key[1], "cost_usd": 0.0, "tokens": 0, "calls": 0})
        m["cost_usd"] += cost or 0.0
        m["tokens"] += tokens
        m["calls"] += 1

        feature_key = row.get("feature") or "unknown"
        f = by_feature.setdefault(feature_key, {"feature": feature_key, "cost_usd": 0.0, "tokens": 0, "calls": 0})
        f["cost_usd"] += cost or 0.0
        f["tokens"] += tokens
        f["calls"] += 1

    return {
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "unknown_cost_calls": unknown_cost_calls,
        "by_model": sorted(by_model.values(), key=lambda r: r["cost_usd"], reverse=True),
        "by_feature": sorted(by_feature.values(), key=lambda r: r["cost_usd"], reverse=True),
    }


@router.get("/api/usage/llm")
async def usage_llm(user: dict[str, Any] = Depends(require_user)):
    """Cost/token breakdown for the usage popup — sourced from the llm_calls
    ledger (app/core/llm.py writes one row per call), unlike GET /api/usage
    which reads token totals off the messages table for the quota gate."""
    month_start = _month_start_iso()
    week_start = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()

    month_res = (
        supabase.table("llm_calls")
        .select("provider, model, feature, total_tokens, cost_usd")
        .eq("user_id", user["id"])
        .gte("created_at", month_start)
        .execute()
    )
    week_res = (
        supabase.table("llm_calls")
        .select("provider, model, feature, total_tokens, cost_usd")
        .eq("user_id", user["id"])
        .gte("created_at", week_start)
        .execute()
    )
    return {
        "month": _aggregate_llm_calls(month_res.data or []),
        "last_7_days": _aggregate_llm_calls(week_res.data or []),
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
    request: Request,
    body: KinApiMessageRequest,
    authorization: Optional[str] = Header(None),
):
    """Programmatic access to a user's own Kin, authenticated with a Kin API
    key instead of a Supabase session — free on every plan (used to be
    Executive-only; see main.py's MAX_KIN_API_KEYS comment for why opening
    it up doesn't change the actual abuse surface). Counts against the same
    monthly token quota as web chat, since it runs the exact same model
    calls — that quota is this endpoint's real usage cap, same as it is for
    everyone using Kin through the browser.

    Enforces the limits documented in the OpenAPI description
    (app/core/app_factory.py): 60 req/min per key, 120 req/min per IP, the
    key's `scopes`, and its `allowed_ips` — previously these checks existed
    in app/core/security.py but were never actually called from here (or
    anywhere), so none of it was really enforced. Every request is also
    audit-logged to kin_api_audit_log (best-effort, never blocks the reply).
    """
    started = time.monotonic()
    status_code = 200
    key_row: Optional[dict[str, Any]] = None
    try:
        # Per-IP limit applies before we even know which key this is —
        # matches "120 requests/minute per IP address across all public
        # endpoints" in the docs (a single IP hammering with many different
        # keys is still capped).
        _sec.check_ip_rate(request, limit=120, window=60)

        key_row = _resolve_kin_api_key(authorization)
        _sec.check_key_rate(key_row["id"], limit=60, window=60)
        _sec.check_ip_allowlist(key_row, request)
        _sec.check_scope(key_row, "chat")

        user_res = supabase.table("users").select("*").eq("id", key_row["user_id"]).execute()
        if not user_res.data:
            status_code = 401
            raise HTTPException(status_code=401, detail="API key owner not found")
        user = user_res.data[0]

        used, limit = quota_state(user)
        if used >= limit:
            status_code = 429
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
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        _sec.log_api_access(
            supabase,
            key_id=(key_row or {}).get("id", ""),
            user_id=(key_row or {}).get("user_id"),
            endpoint="/api/v1/messages",
            method="POST",
            client_ip=_sec.client_ip(request),
            request_id=_sec.get_request_id(request),
            status_code=status_code,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


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
