from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import string
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from plugins import social_providers as sp

from app.core import security as _sec
from app.core.clients import supabase
from app.core.config import FUNCTION_SECRET, MODEL_NAME
from app.core.deps import require_user
from app.core.llm import complete as llm_complete, parsed_tool_calls
from app.schemas.social import (
    SocialAgentMessageCreate,
    SocialAgentThreadCreate,
    SocialAutoPostCreate,
    SocialPostCreate,
    SocialPostUpdate,
    SocialSetCreate,
    SocialShortenContentRequest,
    SocialShortlinkCreate,
    SocialSignatureCreate,
    SocialTagCreate,
    SocialWebhookSave,
)

from main import (
    _credentials_fernet,
    _decode_credentials_payload,
    _decode_state,
    _decode_state_claim,
    _mint_state,
)

logger = logging.getLogger("kin")

router = APIRouter()


# ---------------------------------------------------------------------------
# Social account credentials — stored in social_accounts (NOT the generic
# user_credentials table, which is shared with the unrelated BYOK/integration
# marketplace system and enforces one row per user+slug). social_accounts has
# no such constraint, so a user can connect any number of accounts on the
# same platform. Fernet-encrypted via _credentials_fernet(), same scheme as
# the Google/Microsoft OAuth route above (_mint_state/_decode_state).
# ---------------------------------------------------------------------------


def _read_social_account_credentials(account_id: str, user_id: str) -> Optional[dict[str, Any]]:
    res = (
        supabase.table("social_accounts")
        .select("encrypted_payload, expires_at")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        return None
    creds = _decode_credentials_payload(res.data["encrypted_payload"])
    creds["_expires_at"] = res.data.get("expires_at")
    return creds


def _encrypt_social_payload(payload: dict[str, Any]) -> tuple[str, Optional[str]]:
    payload = {k: v for k, v in payload.items() if not k.startswith("_")}
    plaintext = json.dumps(payload).encode()
    ciphertext = _credentials_fernet().encrypt(plaintext)
    expires_at = None
    expires_in = payload.get("expires_in")
    if expires_in:
        try:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
        except (TypeError, ValueError):
            expires_at = None
    return f"\\x{ciphertext.hex()}", expires_at


def _create_social_account(user_id: str, slug: str, payload: dict[str, Any]) -> str:
    """Inserts a NEW social_accounts row (never overwrites an existing one),
    which is what actually allows connecting a second account of the same
    platform. Returns the new account id."""
    encrypted_payload, expires_at = _encrypt_social_payload(payload)
    res = supabase.table("social_accounts").insert({
        "user_id": user_id,
        "slug": slug,
        "auth_type": "oauth" if payload.get("access_token") else "api_key",
        "encrypted_payload": encrypted_payload,
        "expires_at": expires_at,
        "display_name": payload.get("name"),
        "handle": payload.get("username") or payload.get("handle"),
        "avatar_url": payload.get("avatar_url") or payload.get("picture"),
    }).execute()
    return res.data[0]["id"]


def _update_social_account_credentials(account_id: str, payload: dict[str, Any]) -> None:
    encrypted_payload, expires_at = _encrypt_social_payload(payload)
    supabase.table("social_accounts").update({
        "encrypted_payload": encrypted_payload,
        "expires_at": expires_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", account_id).execute()


@router.get("/api/social/accounts")
async def list_social_accounts(user: dict[str, Any] = Depends(require_user)):
    """The real connected accounts (can be N per platform) — used by the
    composer's multi-select and the Active Channels sidebar. Distinct from
    /api/social/integrations below, which lists all 30+ SUPPORTED platforms
    (connected or not) for the Add Channel grid."""
    res = (
        supabase.table("social_accounts")
        .select("id, slug, display_name, handle, avatar_url, created_at")
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    )
    return [
        {
            "id": r["id"],
            "slug": r["slug"],
            "name": sp.PROVIDERS_MAP.get(r["slug"], r["slug"]),
            "displayName": r.get("display_name"),
            "handle": r.get("handle"),
            "avatarUrl": r.get("avatar_url"),
            "connectedAt": r.get("created_at"),
        }
        for r in (res.data or [])
    ]


@router.post("/api/social/accounts/{account_id}/disconnect")
async def social_account_disconnect(account_id: str, user: dict[str, Any] = Depends(require_user)):
    supabase.table("social_accounts").delete().eq("id", account_id).eq("user_id", user["id"]).execute()
    return {"status": "disconnected"}


@router.get("/api/social/integrations")
async def list_social_integrations(user: dict[str, Any] = Depends(require_user)):
    res = (
        supabase.table("social_accounts")
        .select("slug, updated_at, encrypted_payload")
        .eq("user_id", user["id"])
        .execute()
    )
    connected: dict[str, dict[str, Any]] = {}
    for r in res.data or []:
        # Only ever surface display fields (never tokens/secrets) — decrypt,
        # pull out the handful of known-safe keys a provider may have
        # captured at connect time, and discard everything else. When a
        # platform has multiple connected accounts, the most recently
        # updated one wins for this "is it connected" summary list.
        display: dict[str, Any] = {}
        try:
            creds = _decode_credentials_payload(r["encrypted_payload"])
            for key in ("avatar_url", "picture", "username", "name", "handle"):
                if creds.get(key):
                    display[key] = creds[key]
        except Exception:
            logger.debug("Could not decrypt credentials for integrations list (slug=%s)", r["slug"])
        prior = connected.get(r["slug"])
        if not prior or r["updated_at"] > prior["updated_at"]:
            connected[r["slug"]] = {"updated_at": r["updated_at"], **display}

    return [
        {
            "slug": slug,
            "name": name,
            "connected": slug in connected,
            "connectedAt": connected.get(slug, {}).get("updated_at"),
            "avatarUrl": connected.get(slug, {}).get("avatar_url") or connected.get(slug, {}).get("picture"),
            "handle": connected.get(slug, {}).get("username") or connected.get(slug, {}).get("handle"),
            "displayName": connected.get(slug, {}).get("name"),
            "oauth2": sp.get_provider(slug).oauth2,
            "real": sp.is_real_provider(slug),
            "comment": sp.get_provider(slug).supports_comment,
            "mention": sp.get_provider(slug).supports_mention,
        }
        for slug, name in sp.PROVIDERS_MAP.items()
    ]


@router.post("/api/social/integrations/{slug}/start")
async def social_integration_start(
    slug: str, request: Request, user: dict[str, Any] = Depends(require_user)
):
    provider = sp.get_provider(slug)
    if not provider.oauth2:
        raise HTTPException(
            status_code=400,
            detail=f"{provider.name} does not use OAuth connect; use connect-manual",
        )
    origin = request.headers.get("origin", "")

    extra_claims: dict[str, Any] = {}
    pkce_challenge: Optional[str] = None
    if getattr(provider, "uses_pkce", False):
        pkce_verifier, pkce_challenge = sp.generate_pkce_pair()
        extra_claims["pkce_verifier"] = pkce_verifier

    state = _mint_state(
        user["auth_user_id"], origin_url=origin, redirect_path="/dashboard/social",
        mode="primary", extra_claims=extra_claims,
    )
    try:
        url = (
            provider.generate_auth_url(state, pkce_challenge=pkce_challenge)
            if pkce_challenge
            else provider.generate_auth_url(state)
        )
    except sp.SocialPostError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"url": url}


@router.get("/auth/social/{slug}/callback")
async def social_integration_callback(slug: str, state: str, code: Optional[str] = None):
    auth_user_id, frontend, redirect_path, _mode = _decode_state(state)
    if not auth_user_id:
        return RedirectResponse(f"{frontend}{redirect_path}?social=error&provider={slug}")
    if not code:
        return RedirectResponse(f"{frontend}{redirect_path}?social=error&provider={slug}")

    provider = sp.get_provider(slug)
    try:
        if getattr(provider, "uses_pkce", False):
            pkce_verifier = _decode_state_claim(state, "pkce_verifier")
            creds = await provider.exchange_code(code, "", pkce_verifier=pkce_verifier)
        else:
            creds = await provider.exchange_code(code, "")
    except Exception:
        logger.exception("social oauth exchange failed for %s", slug)
        return RedirectResponse(f"{frontend}{redirect_path}?social=error&provider={slug}")

    user_res = supabase.table("users").select("id").eq("auth_user_id", auth_user_id).execute()
    if not user_res.data:
        return RedirectResponse(f"{frontend}{redirect_path}?social=error&provider={slug}")

    # Always inserts a NEW account row — connecting the same platform twice
    # adds a second account instead of overwriting the first.
    _create_social_account(user_res.data[0]["id"], slug, creds)
    return RedirectResponse(f"{frontend}{redirect_path}?social=ok&provider={slug}")


@router.post("/api/social/integrations/{slug}/connect-manual")
async def social_integration_connect_manual(
    slug: str, body: dict[str, Any] = Body(default={}), user: dict[str, Any] = Depends(require_user)
):
    provider = sp.get_provider(slug)
    if provider.oauth2:
        raise HTTPException(status_code=400, detail=f"{provider.name} uses OAuth connect; use start")
    try:
        creds = await provider.connect_manual(body)
    except sp.SocialPostError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError:
        raise HTTPException(status_code=501, detail=f"{provider.name} is not yet supported")
    _create_social_account(user["id"], slug, creds)
    return {"status": "connected"}


@router.post("/api/social/integrations/{slug}/disconnect")
async def social_integration_disconnect(slug: str, user: dict[str, Any] = Depends(require_user)):
    # Legacy slug-keyed disconnect: removes every account on this platform.
    # The Active Channels sidebar uses the id-keyed /api/social/accounts/{id}/disconnect
    # instead so a single account can be disconnected without affecting siblings.
    supabase.table("social_accounts").delete().eq("user_id", user["id"]).eq("slug", slug).execute()
    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# Social outbound webhooks — fired by /cron/publish-social-posts on
# post.published / post.failed (see _fire_social_webhook above).
# ---------------------------------------------------------------------------


@router.get("/api/social/webhook")
async def get_social_webhook(user: dict[str, Any] = Depends(require_user)):
    # postgrest-py's maybe_single().execute() returns None outright (not a
    # response object with .data = None) when the query matches zero rows —
    # a quirk of how it handles the empty-body 204 response, not something
    # callers should have to know about at every call site.
    res = (
        supabase.table("social_webhooks")
        .select("id, url, active, created_at")
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    return res.data if res else None


@router.post("/api/social/webhook")
async def save_social_webhook(body: SocialWebhookSave, user: dict[str, Any] = Depends(require_user)):
    from app.core.url_safety import UnsafeURLError, assert_safe_url

    if not body.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must be https://")
    try:
        assert_safe_url(body.url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or disallowed webhook URL: {exc}")
    secret = secrets.token_hex(24)
    existing = (
        supabase.table("social_webhooks").select("secret").eq("user_id", user["id"]).maybe_single().execute()
    )
    if existing.data:
        secret = existing.data.get("secret") or secret
    supabase.table("social_webhooks").upsert({
        "user_id": user["id"],
        "url": body.url,
        "active": body.active,
        "secret": secret,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id").execute()
    return {"status": "saved", "secret": secret}


@router.delete("/api/social/webhook")
async def delete_social_webhook(user: dict[str, Any] = Depends(require_user)):
    supabase.table("social_webhooks").delete().eq("user_id", user["id"]).execute()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Social Copilot — a real multi-turn, tool-calling chat agent (replaces the
# old one-shot "generate 3 outlines" form). The agent can look up the user's
# connected accounts and recent posts, suggest open posting times, and
# actually schedule/draft a post — see SOCIAL_AGENT_TOOLS below. Built on
# app/core/llm.py's OpenAI-shaped complete()/tools=/parsed_tool_calls(),
# not main.py's Gemini-native run_assistant loop (that one is the
# general-purpose Kin assistant with its own RAG/memory/history plumbing —
# reusing it here would couple this feature to a lot of unrelated machinery
# for no benefit, since this agent's tools and grounding are entirely
# social-specific).
# ---------------------------------------------------------------------------

SOCIAL_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_connected_accounts",
            "description": (
                "List the user's connected social media accounts (id, platform, handle). "
                "Use this to find the exact account_id(s) to target before scheduling a post."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_posts",
            "description": "List the user's recent social posts, optionally filtered by state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max posts to return, default 10, max 25"},
                    "state": {"type": "string", "enum": ["draft", "queue", "published", "failed"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_best_times",
            "description": (
                "Suggest upcoming open posting time slots for one connected account, avoiding "
                "collisions with anything already scheduled for it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "count": {"type": "integer", "description": "How many slots to return, default 3, max 10"},
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_post",
            "description": (
                "Create a social post for one or more connected accounts. Always confirm the exact "
                "content, target account(s), and publish time back to the user before calling this, "
                "unless they were fully explicit about all three already."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_ids": {
                        "type": "array", "items": {"type": "string"},
                        "description": "One or more account ids from list_connected_accounts",
                    },
                    "content": {"type": "string"},
                    "publish_date": {"type": "string", "description": "ISO-8601 datetime, UTC"},
                    "state": {
                        "type": "string", "enum": ["draft", "queue"],
                        "description": "'queue' to actually schedule it, 'draft' to save without scheduling",
                    },
                },
                "required": ["account_ids", "content", "publish_date"],
            },
        },
    },
]

_SOCIAL_AGENT_MAX_ROUNDS = 5
_SOCIAL_AGENT_SYSTEM_PROMPT = (
    "You are Kin's Social Copilot, a chat assistant that helps the user plan, draft, and schedule "
    "social media posts across their connected accounts. You can call tools to look up real connected "
    "accounts, recent posts, suggest open posting times, and actually schedule/draft a post.\n\n"
    "Rules:\n"
    "- Never invent an account_id — call list_connected_accounts first if you don't already know it "
    "from this conversation or from the accounts list below.\n"
    "- Before calling schedule_post, restate the content, target account(s), and publish time back to "
    "the user unless they were fully explicit about all three in their message.\n"
    "- publish_date must be ISO-8601 in UTC.\n"
    "- Keep replies concise and conversational."
)


async def _execute_social_agent_tool(user: dict[str, Any], name: str, args: dict[str, Any]) -> dict[str, Any]:
    user_id = user["id"]

    if name == "list_connected_accounts":
        res = (
            supabase.table("social_accounts")
            .select("id, slug, display_name, handle")
            .eq("user_id", user_id)
            .execute()
        )
        return {"accounts": res.data or []}

    if name == "list_recent_posts":
        limit = max(1, min(int(args.get("limit") or 10), 25))
        query = (
            supabase.table("social_posts")
            .select("id, integration_slug, content, state, publish_date")
            .eq("user_id", user_id)
            .order("publish_date", desc=True)
            .limit(limit)
        )
        state = args.get("state")
        if state:
            query = query.eq("state", state)
        return {"posts": query.execute().data or []}

    if name == "suggest_best_times":
        account_id = args.get("account_id")
        if not account_id:
            return {"error": "account_id is required"}
        acct = (
            supabase.table("social_accounts")
            .select("id")
            .eq("id", account_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not acct.data:
            return {"error": f"unknown account_id: {account_id}"}
        return {"slots": _compute_best_time_slots(account_id, int(args.get("count") or 3))}

    if name == "schedule_post":
        account_ids = [a for a in (args.get("account_ids") or []) if isinstance(a, str)]
        content = (args.get("content") or "").strip()
        publish_date = args.get("publish_date")
        state = args.get("state") if args.get("state") in ("draft", "queue") else "queue"
        if not account_ids or not content or not publish_date:
            return {"error": "account_ids, content, and publish_date are all required"}
        accts_res = (
            supabase.table("social_accounts")
            .select("id, slug")
            .eq("user_id", user_id)
            .in_("id", account_ids)
            .execute()
        )
        slug_by_id = {a["id"]: a["slug"] for a in (accts_res.data or [])}
        missing = [a for a in account_ids if a not in slug_by_id]
        if missing:
            return {"error": f"unknown or unauthorized account_id(s): {missing}"}
        rows = [
            {
                "user_id": user_id,
                "integration_slug": slug_by_id[aid],
                "social_account_id": aid,
                "content": content,
                "publish_date": publish_date,
                "state": state,
            }
            for aid in account_ids
        ]
        res = supabase.table("social_posts").insert(rows).execute()
        return {"created": res.data or []}

    return {"error": f"unknown tool: {name}"}


def _describe_tool_action(name: str, args: dict[str, Any], result: dict[str, Any]) -> str:
    """Plain-language summary of one tool call, for display_log — the UI
    renders this directly instead of parsing raw tool-call/response JSON."""
    if name == "schedule_post":
        if result.get("error"):
            return f"Couldn't schedule the post: {result['error']}"
        n = len(result.get("created") or [])
        verb = "Drafted" if args.get("state") == "draft" else "Scheduled"
        return f"{verb} {n} post{'s' if n != 1 else ''}."
    if name == "list_connected_accounts":
        return f"Looked up connected accounts ({len(result.get('accounts') or [])} found)."
    if name == "list_recent_posts":
        return f"Looked up recent posts ({len(result.get('posts') or [])} found)."
    if name == "suggest_best_times":
        if result.get("error"):
            return f"Couldn't suggest times: {result['error']}"
        return f"Suggested {len(result.get('slots') or [])} open posting time(s)."
    return f"Ran {name}."


async def _run_social_agent_turn(
    user: dict[str, Any], messages: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Runs the tool-calling loop for one user turn. `messages` is the full
    conversation to send (system + capped history + the new user message),
    and is mutated in place with every assistant/tool turn the loop
    produces. Returns (final_reply_text, messages, action_log) where
    action_log is [{"tool", "args", "result", "summary"}, ...] — one entry
    per tool call actually made this turn."""
    action_log: list[dict[str, Any]] = []
    for _ in range(_SOCIAL_AGENT_MAX_ROUNDS):
        result = await llm_complete(
            model=MODEL_NAME,
            messages=messages,
            tools=SOCIAL_AGENT_TOOLS,
            temperature=0.4,
            max_tokens=800,
            feature="social_agent",
            user_id=user["id"],
        )
        calls = parsed_tool_calls(result)
        if not calls:
            messages.append({"role": "assistant", "content": result.text})
            return result.text, messages, action_log

        messages.append({
            "role": "assistant",
            "content": result.text or None,
            "tool_calls": [
                {
                    "id": c["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": c["name"], "arguments": json.dumps(c["args"], default=str)},
                }
                for i, c in enumerate(calls)
            ],
        })
        for i, c in enumerate(calls):
            call_id = c["id"] or f"call_{i}"
            try:
                output = await _execute_social_agent_tool(user, c["name"], c["args"])
            except Exception as e:  # noqa: BLE001 — a tool failure shouldn't crash the whole turn
                logger.exception("social agent tool %s failed", c["name"])
                output = {"error": str(e)}
            action_log.append({
                "tool": c["name"], "args": c["args"], "result": output,
                "summary": _describe_tool_action(c["name"], c["args"], output),
            })
            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(output, default=str)})

    return (
        "I wasn't able to finish that in one go — try breaking your request into smaller steps.",
        messages,
        action_log,
    )


def _agent_thread_summary(row: dict[str, Any]) -> dict[str, Any]:
    preview = ""
    for entry in reversed(row.get("display_log") or []):
        if entry.get("content"):
            preview = entry["content"][:120]
            break
    return {
        "id": row["id"],
        "title": row.get("title"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "preview": preview,
    }


@router.get("/api/social/agent/threads")
async def list_agent_threads(user: dict[str, Any] = Depends(require_user)):
    res = (
        supabase.table("social_agent_threads")
        .select("id, title, display_log, created_at, updated_at")
        .eq("user_id", user["id"])
        .order("updated_at", desc=True)
        .execute()
    )
    return [_agent_thread_summary(r) for r in (res.data or [])]


@router.post("/api/social/agent/threads")
async def create_agent_thread(
    body: SocialAgentThreadCreate, user: dict[str, Any] = Depends(require_user)
):
    res = supabase.table("social_agent_threads").insert({
        "user_id": user["id"],
        "title": body.title,
    }).execute()
    row = res.data[0]
    return {
        "id": row["id"], "title": row.get("title"), "display_log": [],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


@router.get("/api/social/agent/threads/{thread_id}")
async def get_agent_thread(thread_id: str, user: dict[str, Any] = Depends(require_user)):
    res = (
        supabase.table("social_agent_threads")
        .select("id, title, display_log, created_at, updated_at")
        .eq("id", thread_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    # See get_social_webhook's comment: maybe_single().execute() returns
    # None outright (not a response with .data = None) on zero matching rows.
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    return res.data


@router.delete("/api/social/agent/threads/{thread_id}")
async def delete_agent_thread(thread_id: str, user: dict[str, Any] = Depends(require_user)):
    supabase.table("social_agent_threads").delete().eq("id", thread_id).eq("user_id", user["id"]).execute()
    return {"success": True}


@router.post("/api/social/agent/threads/{thread_id}/messages")
async def send_agent_message(
    thread_id: str, body: SocialAgentMessageCreate, user: dict[str, Any] = Depends(require_user)
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    thread_res = (
        supabase.table("social_agent_threads")
        .select("id, title, messages, display_log")
        .eq("id", thread_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not thread_res or not thread_res.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread = thread_res.data

    accounts_res = (
        supabase.table("social_accounts")
        .select("slug, display_name, handle")
        .eq("user_id", user["id"])
        .execute()
    )
    accounts_summary = ", ".join(
        f"{a.get('display_name') or a.get('handle') or a['slug']} ({a['slug']})"
        for a in (accounts_res.data or [])
    ) or "none connected yet"
    system_prompt = (
        f"{_SOCIAL_AGENT_SYSTEM_PROMPT}\n\n"
        f"Current UTC time: {datetime.now(timezone.utc).isoformat()}\n"
        f"User's connected accounts: {accounts_summary}"
    )

    stored_messages: list[dict[str, Any]] = thread.get("messages") or []
    new_user_message = {"role": "user", "content": content}
    # Cap what's actually SENT to the model each turn to keep prompts
    # bounded — full history still accumulates in both `messages` (rebuilt
    # from stored_messages below) and display_log regardless.
    llm_messages = (
        [{"role": "system", "content": system_prompt}] + stored_messages[-24:] + [new_user_message]
    )
    sent_length = len(llm_messages)

    display_log: list[dict[str, Any]] = thread.get("display_log") or []
    display_log.append({"role": "user", "content": content})

    try:
        reply_text, updated_messages, action_log = await _run_social_agent_turn(user, llm_messages)
    except Exception as e:
        logger.exception("social agent turn failed")
        raise HTTPException(status_code=502, detail=str(e))

    for action in action_log:
        display_log.append({"role": "action", "tool": action["tool"], "content": action["summary"]})
    display_log.append({"role": "assistant", "content": reply_text})

    # Only the turns this round actually added (system + capped history
    # were already in stored_messages or intentionally excluded from it).
    new_turns = updated_messages[sent_length:]
    new_stored_messages = stored_messages + [new_user_message] + new_turns

    update_data: dict[str, Any] = {"messages": new_stored_messages, "display_log": display_log}
    if not thread.get("title"):
        update_data["title"] = content[:60]
    updated_res = (
        supabase.table("social_agent_threads").update(update_data).eq("id", thread_id).execute()
    )
    row = updated_res.data[0] if updated_res.data else {**thread, **update_data}
    return {
        "id": thread_id,
        "title": row.get("title"),
        "display_log": display_log,
        "updated_at": row.get("updated_at"),
    }


@router.get("/api/social/posts")
async def get_social_posts(
    state: Optional[str] = None,
    user: dict[str, Any] = Depends(require_user)
):
    try:
        query = supabase.table("social_posts").select("*").eq("user_id", user["id"])
        if state:
            query = query.eq("state", state)
        res = query.order("publish_date", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query social posts")
        raise HTTPException(status_code=500, detail=str(e))

def _shift_interval(dt: datetime, interval: str, n: int) -> datetime:
    if interval == "daily":
        return dt + timedelta(days=n)
    if interval == "weekly":
        return dt + timedelta(weeks=n)
    if interval == "monthly":
        month0 = dt.month - 1 + n
        year = dt.year + month0 // 12
        month = month0 % 12 + 1
        day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                           31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return dt.replace(year=year, month=month, day=day)
    return dt


async def _create_social_post_rows(user_id: str, body: SocialPostCreate) -> Any:
    """Shared by the dashboard's POST /api/social/posts (JWT-authed) and the
    public API's POST /api/v1/social/posts (API-key-authed) — same
    validation and insert logic regardless of caller."""
    try:
        account_ids = list(body.social_account_ids or [])

        # Legacy fallback for any caller still sending a bare integration_slug
        # (no social_account_ids): resolve it to that user's most-recently
        # connected account of that platform.
        if not account_ids and body.integration_slug:
            fallback = (
                supabase.table("social_accounts")
                .select("id")
                .eq("user_id", user_id)
                .eq("slug", body.integration_slug)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if fallback.data:
                account_ids = [fallback.data[0]["id"]]

        if not account_ids:
            raise HTTPException(status_code=400, detail="No connected social account specified")

        accounts_res = (
            supabase.table("social_accounts")
            .select("id, slug")
            .eq("user_id", user_id)
            .in_("id", account_ids)
            .execute()
        )
        slug_by_id = {a["id"]: a["slug"] for a in (accounts_res.data or [])}
        missing = [aid for aid in account_ids if aid not in slug_by_id]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown or unauthorized social account(s): {missing}")

        overrides = body.content_overrides or {}
        # One social_posts row per selected account, sharing a group_id so the
        # UI can recognize them later as "one post, N channels" if it ever
        # needs to (calendar/list already display them as separate cards,
        # matching Postiz's own per-platform post rows).
        group_id = str(uuid.uuid4()) if len(account_ids) > 1 else None

        rows = [
            {
                "user_id": user_id,
                "integration_slug": slug_by_id[account_id],
                "social_account_id": account_id,
                "group_id": group_id,
                "content": overrides.get(account_id, body.content),
                "publish_date": body.publish_date,
                "state": body.state,
                "image_url": body.image_url,
                "media_type": body.media_type,
                "parent_post_id": body.parent_post_id,
                "settings": body.settings,
            }
            for account_id in account_ids
        ]
        res = supabase.table("social_posts").insert(rows).execute()
        created = res.data or []

        # Repeat posts are independent future posts (not threaded replies),
        # capped at 12 total occurrences to prevent runaway scheduling.
        if body.repeat_interval and body.repeat_count and body.repeat_count > 1 and not body.parent_post_id:
            base_date = datetime.fromisoformat(body.publish_date.replace("Z", "+00:00"))
            repeats = [
                {
                    "user_id": user_id,
                    "integration_slug": slug_by_id[account_id],
                    "social_account_id": account_id,
                    "group_id": group_id,
                    "content": overrides.get(account_id, body.content),
                    "publish_date": _shift_interval(base_date, body.repeat_interval, i).isoformat(),
                    "state": body.state,
                    "image_url": body.image_url,
                    "media_type": body.media_type,
                    "settings": body.settings,
                }
                for account_id in account_ids
                for i in range(1, min(body.repeat_count, 12))
            ]
            if repeats:
                supabase.table("social_posts").insert(repeats).execute()

        # Preserve the old single-object response shape when only one account
        # was targeted (the common case, and what most existing frontend code
        # expects); return the array when it's a real multi-account submit.
        return created[0] if len(created) == 1 else created
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create social post")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/social/posts")
async def create_social_post(body: SocialPostCreate, user: dict[str, Any] = Depends(require_user)):
    return await _create_social_post_rows(user["id"], body)

@router.patch("/api/social/posts/{post_id}")
async def update_social_post(post_id: str, body: SocialPostUpdate, user: dict[str, Any] = Depends(require_user)):
    try:
        update_data = {}
        if body.content is not None:
            update_data["content"] = body.content
        if body.publish_date is not None:
            update_data["publish_date"] = body.publish_date
        if body.state is not None:
            update_data["state"] = body.state
        if body.image_url is not None:
            update_data["image_url"] = body.image_url
        if body.media_type is not None:
            update_data["media_type"] = body.media_type
        if body.settings is not None:
            update_data["settings"] = body.settings

        res = supabase.table("social_posts").update(update_data).eq("id", post_id).eq("user_id", user["id"]).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        logger.exception("Failed to update social post")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/social/posts/{post_id}")
async def delete_social_post(post_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("social_posts").delete().eq("id", post_id).eq("user_id", user["id"]).execute()
        return {"success": True}
    except Exception as e:
        logger.exception("Failed to delete social post")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/social/auto-posts")
async def get_social_auto_posts(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("social_auto_posts").select("*").eq("user_id", user["id"]).execute()
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query social auto posts")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/social/auto-posts")
async def create_social_auto_post(body: SocialAutoPostCreate, user: dict[str, Any] = Depends(require_user)):
    from app.core.url_safety import UnsafeURLError, assert_safe_url

    try:
        assert_safe_url(body.url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or disallowed feed URL: {exc}")

    try:
        auto_data = {
            "user_id": user["id"],
            "title": body.title,
            "url": body.url,
            "active": body.active,
            "generate_content": body.generate_content,
            "integrations": body.integrations
        }
        res = supabase.table("social_auto_posts").insert(auto_data).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        logger.exception("Failed to create social auto post")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/social/auto-posts/{id}")
async def delete_social_auto_post(id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("social_auto_posts").delete().eq("id", id).eq("user_id", user["id"]).execute()
        return {"success": True}
    except Exception as e:
        logger.exception("Failed to delete social auto post")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/social/tags")
async def get_social_tags(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("social_tags").select("*").eq("user_id", user["id"]).execute()
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query social tags")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/social/tags")
async def create_social_tag(body: SocialTagCreate, user: dict[str, Any] = Depends(require_user)):
    try:
        tag_data = {
            "user_id": user["id"],
            "name": body.name,
            "color": body.color
        }
        res = supabase.table("social_tags").insert(tag_data).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        logger.exception("Failed to create social tag")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Signatures — reusable text snippets inserted into the composer, optionally
# auto-filled into new posts (Postiz's Signatures.autoAdd).
# ---------------------------------------------------------------------------


@router.get("/api/social/signatures")
async def get_social_signatures(user: dict[str, Any] = Depends(require_user)):
    try:
        res = (
            supabase.table("social_signatures")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query social signatures")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/social/signatures")
async def create_social_signature(body: SocialSignatureCreate, user: dict[str, Any] = Depends(require_user)):
    try:
        content = body.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        # Only one signature can auto-add at a time — turning this one on
        # turns any previous one off, same as Postiz.
        if body.auto_add:
            supabase.table("social_signatures").update({"auto_add": False}).eq("user_id", user["id"]).execute()
        res = supabase.table("social_signatures").insert({
            "user_id": user["id"],
            "content": content,
            "auto_add": body.auto_add,
        }).execute()
        return res.data[0] if res.data else {}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create social signature")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/social/signatures/{signature_id}")
async def delete_social_signature(signature_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("social_signatures").delete().eq("id", signature_id).eq("user_id", user["id"]).execute()
        return {"success": True}
    except Exception as e:
        logger.exception("Failed to delete social signature")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Sets — reusable post templates (content + media) the composer can save to
# and load from (Postiz's Sets).
# ---------------------------------------------------------------------------


@router.get("/api/social/sets")
async def get_social_sets(user: dict[str, Any] = Depends(require_user)):
    try:
        res = (
            supabase.table("social_sets")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query social sets")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/social/sets")
async def create_social_set(body: SocialSetCreate, user: dict[str, Any] = Depends(require_user)):
    try:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        res = supabase.table("social_sets").insert({
            "user_id": user["id"],
            "name": name,
            "content": body.content,
            "image_url": body.image_url,
            "media_type": body.media_type,
        }).execute()
        return res.data[0] if res.data else {}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create social set")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/social/sets/{set_id}")
async def delete_social_set(set_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("social_sets").delete().eq("id", set_id).eq("user_id", user["id"]).execute()
        return {"success": True}
    except Exception as e:
        logger.exception("Failed to delete social set")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Shortlinks — Kin's own redirect-and-count link shortener, driving the
# composer's "Shorten links" action (a simplified, per-post-opt-in version
# of Postiz's org-level Organization.shortlink preference). /l/{code} is
# public (no auth — it has to work when clicked from a live social post).
# ---------------------------------------------------------------------------

_SHORTLINK_CODE_ALPHABET = string.ascii_letters + string.digits
_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")


def _generate_shortlink_code(length: int = 7) -> str:
    return "".join(secrets.choice(_SHORTLINK_CODE_ALPHABET) for _ in range(length))


@router.post("/api/social/shortlinks")
async def create_social_shortlink(
    body: SocialShortlinkCreate, request: Request, user: dict[str, Any] = Depends(require_user)
):
    from app.core.url_safety import UnsafeURLError, assert_safe_url

    target_url = body.url.strip()
    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    try:
        assert_safe_url(target_url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or disallowed URL: {exc}")

    for _ in range(5):
        code = _generate_shortlink_code()
        try:
            res = supabase.table("social_shortlinks").insert({
                "user_id": user["id"],
                "code": code,
                "target_url": target_url,
            }).execute()
            short_url = f"{str(request.base_url).rstrip('/')}/l/{res.data[0]['code']}"
            return {"code": res.data[0]["code"], "shortUrl": short_url, "targetUrl": target_url}
        except Exception:
            continue  # code collision (rare) — try another
    raise HTTPException(status_code=500, detail="Could not generate a unique short link, try again")


@router.post("/api/social/shortlinks/expand-post")
async def shorten_links_in_post_content(
    body: SocialShortenContentRequest, request: Request, user: dict[str, Any] = Depends(require_user)
):
    """Convenience endpoint for the composer's "Shorten links" button: takes
    the whole post body, shortens every http(s) link found in it, and
    returns the rewritten text. Each match gets its own /l/{code} row so
    clicks are tracked per-link."""
    text = body.content
    urls = list(dict.fromkeys(_URL_PATTERN.findall(text)))  # de-duped, order-preserved
    if not urls:
        return {"content": text, "shortened": 0}

    from app.core.url_safety import UnsafeURLError, assert_safe_url

    base = str(request.base_url).rstrip("/")
    for original in urls:
        try:
            assert_safe_url(original)
        except UnsafeURLError:
            continue  # leave unsafe/disallowed URLs untouched rather than failing the whole post
        for _ in range(5):
            code = _generate_shortlink_code()
            try:
                supabase.table("social_shortlinks").insert({
                    "user_id": user["id"],
                    "code": code,
                    "target_url": original,
                }).execute()
                text = text.replace(original, f"{base}/l/{code}")
                break
            except Exception:
                continue
    return {"content": text, "shortened": len(urls)}


@router.get("/l/{code}")
async def resolve_shortlink(code: str):
    res = supabase.table("social_shortlinks").select("id, target_url, clicks").eq("code", code).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Link not found")
    supabase.table("social_shortlinks").update({"clicks": (res.data.get("clicks") or 0) + 1}).eq("id", res.data["id"]).execute()
    return RedirectResponse(res.data["target_url"], status_code=302)


# ---------------------------------------------------------------------------
# @-mention autocomplete — see supports_mention on SocialProvider. Only
# platforms with a real user-search API implement this (Bluesky, Mastodon);
# everything else just returns an empty list.
# ---------------------------------------------------------------------------


@router.get("/api/social/mentions")
async def search_social_mentions(
    account_id: str, q: str, user: dict[str, Any] = Depends(require_user)
):
    query = q.strip()
    if len(query) < 2:
        return []
    account_res = (
        supabase.table("social_accounts")
        .select("slug")
        .eq("id", account_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not account_res.data:
        raise HTTPException(status_code=404, detail="Account not found")
    slug = account_res.data["slug"]
    provider = sp.get_provider(slug)
    if not provider.supports_mention:
        return []
    credentials = _read_social_account_credentials(account_id, user["id"])
    if not credentials:
        return []
    credentials.pop("_expires_at", None)
    try:
        return await provider.mention(query, credentials)
    except Exception:
        logger.exception("Mention search failed for account %s", account_id)
        return []


# ---------------------------------------------------------------------------
# Best-time-to-post — a fixed set of daily posting-time slots (Postiz's own
# Integration.postingTimes default is likewise a fixed array, not something
# derived from engagement data), walked forward day by day and filtered
# against that account's already-scheduled posts so suggestions don't
# collide with something already queued.
# ---------------------------------------------------------------------------

# Minutes past midnight (UTC): 09:00, 13:00, 18:00.
_DEFAULT_POSTING_TIMES_MINUTES = [9 * 60, 13 * 60, 18 * 60]
_BEST_TIME_COLLISION_WINDOW = timedelta(minutes=30)


def _compute_best_time_slots(account_id: str, count: int) -> list[str]:
    """Core slot-finding logic, shared by the /api/social/best-time endpoint
    and the agent's suggest_best_times tool (see SOCIAL_AGENT_TOOLS below).
    Caller is responsible for verifying the account belongs to the
    requesting user before calling this."""
    count = max(1, min(count, 10))
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=14)
    scheduled_res = (
        supabase.table("social_posts")
        .select("publish_date")
        .eq("social_account_id", account_id)
        .in_("state", ["queue", "draft"])
        .gte("publish_date", now.isoformat())
        .lte("publish_date", horizon.isoformat())
        .execute()
    )
    taken: list[datetime] = []
    for row in scheduled_res.data or []:
        try:
            taken.append(datetime.fromisoformat(row["publish_date"].replace("Z", "+00:00")))
        except (TypeError, ValueError):
            continue

    slots: list[str] = []
    day_offset = 0
    while len(slots) < count and day_offset < 14:
        day = (now + timedelta(days=day_offset)).date()
        for minutes in _DEFAULT_POSTING_TIMES_MINUTES:
            candidate = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=minutes)
            if candidate <= now:
                continue
            if any(abs((candidate - t).total_seconds()) < _BEST_TIME_COLLISION_WINDOW.total_seconds() for t in taken):
                continue
            slots.append(candidate.isoformat())
            if len(slots) >= count:
                break
        day_offset += 1

    return slots


@router.get("/api/social/best-time")
async def suggest_best_times(
    account_id: str, count: int = 3, user: dict[str, Any] = Depends(require_user)
):
    account_res = (
        supabase.table("social_accounts")
        .select("id")
        .eq("id", account_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not account_res.data:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"slots": _compute_best_time_slots(account_id, count)}


# ===========================================================================
# Public API v1 — programmatic access via a Kin API key (kin_sk_...) instead
# of a Supabase session, following the exact pattern chat.py's
# POST /api/v1/messages already established (see app/core/security.py):
# per-IP rate limit -> resolve key -> per-key rate limit -> IP allowlist ->
# scope check -> business logic -> best-effort audit log. Read endpoints
# need the "read" scope, mutating ones need "write" — see VALID_SCOPES'
# doc comment in security.py. Documented in app/core/app_factory.py's
# OpenAPI description alongside /api/v1/messages.
# ===========================================================================

def _touch_social_api_key(key_row: dict[str, Any]) -> None:
    supabase.table("kin_api_keys").update({
        "last_used_at": datetime.now(timezone.utc).isoformat(),
        "request_count": (key_row.get("request_count") or 0) + 1,
    }).eq("id", key_row["id"]).execute()


@asynccontextmanager
async def _social_api_call(
    request: Request, authorization: Optional[str], scope: str, endpoint: str, method: str
):
    """Runs the shared auth/rate-limit/scope preamble, yields the resolved
    kin_api_keys row, and always writes the audit log entry on the way out —
    every /api/v1/social/* handler just does `async with _social_api_call(...)
    as key_row:` and returns its response from inside the block."""
    started = time.monotonic()
    status_code = 200
    key_row: Optional[dict[str, Any]] = None
    try:
        _sec.check_ip_rate(request, limit=120, window=60)
        key_row = _sec.resolve_kin_api_key(authorization)
        _sec.check_key_rate(key_row["id"], limit=60, window=60)
        _sec.check_ip_allowlist(key_row, request)
        _sec.check_scope(key_row, scope)
        _touch_social_api_key(key_row)
        yield key_row
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        _sec.log_api_access(
            supabase,
            key_id=(key_row or {}).get("id", ""),
            user_id=(key_row or {}).get("user_id"),
            endpoint=endpoint,
            method=method,
            client_ip=_sec.client_ip(request),
            request_id=_sec.get_request_id(request),
            status_code=status_code,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


@router.get("/api/v1/social/accounts")
async def public_api_list_accounts(request: Request, authorization: Optional[str] = Header(None)):
    async with _social_api_call(request, authorization, "read", "/api/v1/social/accounts", "GET") as key_row:
        res = (
            supabase.table("social_accounts")
            .select("id, slug, display_name, handle, avatar_url, created_at")
            .eq("user_id", key_row["user_id"])
            .order("created_at")
            .execute()
        )
        return [
            {
                "id": r["id"],
                "slug": r["slug"],
                "name": sp.PROVIDERS_MAP.get(r["slug"], r["slug"]),
                "displayName": r.get("display_name"),
                "handle": r.get("handle"),
                "avatarUrl": r.get("avatar_url"),
                "connectedAt": r.get("created_at"),
            }
            for r in (res.data or [])
        ]


@router.get("/api/v1/social/posts")
async def public_api_list_posts(
    request: Request, state: Optional[str] = None, authorization: Optional[str] = Header(None)
):
    async with _social_api_call(request, authorization, "read", "/api/v1/social/posts", "GET") as key_row:
        query = supabase.table("social_posts").select("*").eq("user_id", key_row["user_id"])
        if state:
            query = query.eq("state", state)
        res = query.order("publish_date", desc=True).execute()
        return res.data or []


@router.post("/api/v1/social/posts")
async def public_api_create_post(
    request: Request, body: SocialPostCreate, authorization: Optional[str] = Header(None)
):
    async with _social_api_call(request, authorization, "write", "/api/v1/social/posts", "POST") as key_row:
        return await _create_social_post_rows(key_row["user_id"], body)


@router.patch("/api/v1/social/posts/{post_id}")
async def public_api_update_post(
    post_id: str, request: Request, body: SocialPostUpdate, authorization: Optional[str] = Header(None)
):
    async with _social_api_call(
        request, authorization, "write", "/api/v1/social/posts/{post_id}", "PATCH"
    ) as key_row:
        update_data: dict[str, Any] = {}
        if body.content is not None:
            update_data["content"] = body.content
        if body.publish_date is not None:
            update_data["publish_date"] = body.publish_date
        if body.state is not None:
            update_data["state"] = body.state
        if body.image_url is not None:
            update_data["image_url"] = body.image_url
        if body.media_type is not None:
            update_data["media_type"] = body.media_type
        if body.settings is not None:
            update_data["settings"] = body.settings
        res = (
            supabase.table("social_posts")
            .update(update_data)
            .eq("id", post_id)
            .eq("user_id", key_row["user_id"])
            .execute()
        )
        return res.data[0] if res.data else {}


@router.delete("/api/v1/social/posts/{post_id}")
async def public_api_delete_post(post_id: str, request: Request, authorization: Optional[str] = Header(None)):
    async with _social_api_call(
        request, authorization, "write", "/api/v1/social/posts/{post_id}", "DELETE"
    ) as key_row:
        supabase.table("social_posts").delete().eq("id", post_id).eq("user_id", key_row["user_id"]).execute()
        return {"success": True}


@router.post("/api/v1/social/media")
async def public_api_upload_media(
    request: Request, file: UploadFile = File(...), authorization: Optional[str] = Header(None)
):
    async with _social_api_call(request, authorization, "write", "/api/v1/social/media", "POST") as key_row:
        return await _upload_social_media_file(key_row["user_id"], file)


@router.get("/api/v1/social/analytics")
async def public_api_analytics(request: Request, authorization: Optional[str] = Header(None)):
    async with _social_api_call(request, authorization, "read", "/api/v1/social/analytics", "GET") as key_row:
        posts_res = supabase.table("social_posts").select("id").eq("user_id", key_row["user_id"]).execute()
        post_ids = [p["id"] for p in (posts_res.data or [])]
        if not post_ids:
            return {"impressions": 0, "likes": 0, "reposts": 0, "clicks": 0}
        analytics_res = (
            supabase.table("social_analytics")
            .select("impressions, likes, reposts, clicks")
            .in_("post_id", post_ids)
            .execute()
        )
        data = analytics_res.data or []
        return {
            "impressions": sum(d.get("impressions") or 0 for d in data),
            "likes": sum(d.get("likes") or 0 for d in data),
            "reposts": sum(d.get("reposts") or 0 for d in data),
            "clicks": sum(d.get("clicks") or 0 for d in data),
        }


@router.get("/api/v1/social/best-time")
async def public_api_best_time(
    request: Request, account_id: str, count: int = 3, authorization: Optional[str] = Header(None)
):
    async with _social_api_call(request, authorization, "read", "/api/v1/social/best-time", "GET") as key_row:
        account_res = (
            supabase.table("social_accounts")
            .select("id")
            .eq("id", account_id)
            .eq("user_id", key_row["user_id"])
            .maybe_single()
            .execute()
        )
        if not account_res or not account_res.data:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"slots": _compute_best_time_slots(account_id, count)}


# ===========================================================================
# Cron Endpoints for Social Posting (Scheduler & RSS auto-posting)
# ===========================================================================

def _mark_social_post(post_id: str, **fields: Any) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("social_posts").update(fields).eq("id", post_id).execute()


def _record_social_analytics(post_id: str, user_id: str, analytics: dict[str, Any]) -> None:
    """Writes both the current-snapshot row (social_analytics, what the
    summary endpoint reads) and today's rollup row (social_analytics_daily,
    what the trend chart reads) in one place so every analytics write goes
    through the same shape."""
    now_iso = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    counts = {
        "impressions": analytics.get("impressions", 0),
        "likes": analytics.get("likes", 0),
        "reposts": analytics.get("reposts", 0),
        "comments": analytics.get("comments", 0),
        "clicks": analytics.get("clicks", 0),
    }
    supabase.table("social_analytics").upsert({"post_id": post_id, **counts, "updated_at": now_iso}).execute()
    supabase.table("social_analytics_daily").upsert(
        {"post_id": post_id, "user_id": user_id, "day": today, **counts, "updated_at": now_iso},
        on_conflict="post_id,day",
    ).execute()


async def _fire_social_webhook(user_id: str, event: str, post: dict[str, Any]) -> None:
    """Best-effort outbound webhook — never raises, never blocks publishing
    on a slow/broken receiver (short timeout, swallow all errors)."""
    try:
        hook_res = (
            supabase.table("social_webhooks")
            .select("url, secret, active")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        hook = hook_res.data
        if not hook or not hook.get("active") or not hook.get("url"):
            return
        body = json.dumps({
            "event": event,
            "post": {
                "id": post.get("id"),
                "integration_slug": post.get("integration_slug"),
                "state": post.get("state"),
                "release_url": post.get("release_url"),
                "error": post.get("error"),
            },
        })
        headers = {"Content-Type": "application/json"}
        secret = hook.get("secret")
        if secret:
            headers["X-Kin-Signature"] = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        # Re-validate at delivery time, not just at save time (save_social_webhook
        # already checks this, but the URL could point somewhere new by the
        # time it's actually fetched — DNS can change between save and send).
        from app.core.url_safety import UnsafeURLError, assert_safe_url
        assert_safe_url(hook["url"])
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(hook["url"], content=body, headers=headers)
    except UnsafeURLError:
        logger.warning("social webhook URL for user %s is no longer safe to deliver to, skipping", user_id)
    except Exception:
        logger.warning("social webhook delivery failed for user %s", user_id, exc_info=True)


@router.post("/cron/publish-social-posts")
async def cron_publish_social_posts(secret: Optional[str] = None):
    # /cron/* transport stays query-param-only: this URI is registered
    # verbatim in an external Cloud Scheduler job, outside this repo.
    _sec.require_shared_secret(secret, FUNCTION_SECRET)

    try:
        now = datetime.now(timezone.utc)
        # Fetch queued posts that are due
        res = supabase.table("social_posts") \
            .select("*") \
            .eq("state", "queue") \
            .lte("publish_date", now.isoformat()) \
            .execute()
        posts = res.data or []
    except Exception as e:
        logger.exception("Failed to query due social posts")
        raise HTTPException(status_code=500, detail=str(e))

    published_count = 0
    for post in posts:
        try:
            # A thread reply (parent_post_id set) must wait for its parent to
            # be published first, since it posts as a comment on the parent's
            # real platform post id — not a new top-level post.
            parent_release_id: Optional[str] = None
            if post.get("parent_post_id"):
                parent_res = (
                    supabase.table("social_posts")
                    .select("state, release_id")
                    .eq("id", post["parent_post_id"])
                    .maybe_single()
                    .execute()
                )
                parent = parent_res.data or {}
                if parent.get("state") != "published":
                    continue  # retry next cron tick once parent is published
                parent_release_id = parent.get("release_id")

            provider = sp.get_provider(post["integration_slug"])

            account_id = post.get("social_account_id")
            if not account_id:
                # Defensive fallback for any row predating the multi-account
                # migration's backfill — resolve to the most recently
                # connected account of that platform.
                fallback = (
                    supabase.table("social_accounts")
                    .select("id")
                    .eq("user_id", post["user_id"])
                    .eq("slug", post["integration_slug"])
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                account_id = fallback.data[0]["id"] if fallback.data else None

            credentials = _read_social_account_credentials(account_id, post["user_id"]) if account_id else None
            if not credentials:
                _mark_social_post(post["id"], state="failed", error="Integration not connected")
                continue

            expires_at = credentials.pop("_expires_at", None)
            if provider.oauth2 and expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                except ValueError:
                    exp_dt = None
                if exp_dt and exp_dt <= now + timedelta(seconds=60):
                    try:
                        credentials = await provider.refresh_token(credentials)
                        _update_social_account_credentials(account_id, credentials)
                    except sp.NeedsReconnect as e:
                        _mark_social_post(post["id"], state="failed", error=f"Reconnect required: {e}")
                        continue

            try:
                if parent_release_id:
                    result = await provider.comment(parent_release_id, post["content"], credentials)
                else:
                    media_urls = [post["image_url"]] if post.get("image_url") else None
                    result = await provider.post(post["content"], credentials, media_urls, post.get("settings"))
            except sp.NeedsReconnect as e:
                _mark_social_post(post["id"], state="failed", error=f"Reconnect required: {e}")
                await _fire_social_webhook(post["user_id"], "post.failed", {**post, "error": f"Reconnect required: {e}"})
                continue
            except (sp.SocialPostError, NotImplementedError) as e:
                _mark_social_post(post["id"], state="failed", error=str(e))
                await _fire_social_webhook(post["user_id"], "post.failed", {**post, "error": str(e)})
                continue

            _mark_social_post(
                post["id"],
                state="published",
                release_id=result.get("postId"),
                release_url=result.get("releaseURL"),
            )
            await _fire_social_webhook(post["user_id"], "post.published", {
                **post, "state": "published", "release_url": result.get("releaseURL"),
            })

            try:
                analytics = await provider.fetch_analytics(result.get("postId", ""), credentials)
                _record_social_analytics(post["id"], post["user_id"], analytics)
            except Exception:
                logger.exception("Failed to fetch initial analytics for post %s", post["id"])

            published_count += 1

        except Exception as e:
            logger.exception("Failed to publish social post %s", post["id"])
            _mark_social_post(post["id"], state="failed", error=str(e))

    return {"status": "success", "published": published_count}


@router.post("/cron/refresh-social-tokens")
async def cron_refresh_social_tokens(secret: Optional[str] = None):
    """Proactive OAuth token refresh, independent of the publish sweep.

    The publish cron (above) only refreshes a token when a post is actually
    due for that account, so an account with nothing currently scheduled (or
    whose token expires between publish ticks) never gets refreshed and just
    fails the next time it's needed. This sweeps every account whose token
    is expiring soon and refreshes it ahead of time, regardless of whether
    anything is queued.
    """
    # /cron/* transport stays query-param-only: this URI is registered
    # verbatim in an external Cloud Scheduler job, outside this repo.
    _sec.require_shared_secret(secret, FUNCTION_SECRET)

    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(minutes=20)).isoformat()
    try:
        res = (
            supabase.table("social_accounts")
            .select("id, user_id, slug, expires_at")
            .eq("auth_type", "oauth")
            .not_.is_("expires_at", "null")
            .lte("expires_at", horizon)
            .execute()
        )
        accounts = res.data or []
    except Exception as e:
        logger.exception("Failed to query expiring social accounts")
        raise HTTPException(status_code=500, detail=str(e))

    refreshed = 0
    for account in accounts:
        try:
            provider = sp.get_provider(account["slug"])
            if not provider.oauth2:
                continue
            credentials = _read_social_account_credentials(account["id"], account["user_id"])
            if not credentials:
                continue
            credentials.pop("_expires_at", None)
            new_credentials = await provider.refresh_token(credentials)
            _update_social_account_credentials(account["id"], new_credentials)
            refreshed += 1
        except sp.NeedsReconnect:
            logger.warning(
                "social account %s (%s) needs reconnect, skipping proactive refresh",
                account["id"], account["slug"],
            )
        except Exception:
            logger.exception("Failed to proactively refresh social account %s", account["id"])

    return {"status": "success", "refreshed": refreshed}


@router.post("/cron/refresh-social-analytics")
async def cron_refresh_social_analytics(secret: Optional[str] = None):
    """Analytics were previously only ever fetched once, right at publish
    time, so numbers went stale immediately. Re-fetches for everything
    published in the last 30 days."""
    # /cron/* transport stays query-param-only: this URI is registered
    # verbatim in an external Cloud Scheduler job, outside this repo.
    _sec.require_shared_secret(secret, FUNCTION_SECRET)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        res = (
            supabase.table("social_posts")
            .select("id, user_id, integration_slug, social_account_id, release_id")
            .eq("state", "published")
            .gte("updated_at", cutoff)
            .execute()
        )
        posts = res.data or []
    except Exception as e:
        logger.exception("Failed to query published posts for analytics refresh")
        raise HTTPException(status_code=500, detail=str(e))

    refreshed = 0
    for post in posts:
        if not post.get("release_id"):
            continue
        try:
            account_id = post.get("social_account_id")
            if not account_id:
                fallback = (
                    supabase.table("social_accounts")
                    .select("id")
                    .eq("user_id", post["user_id"])
                    .eq("slug", post["integration_slug"])
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                account_id = fallback.data[0]["id"] if fallback.data else None
            credentials = _read_social_account_credentials(account_id, post["user_id"]) if account_id else None
            if not credentials:
                continue
            credentials.pop("_expires_at", None)
            provider = sp.get_provider(post["integration_slug"])
            analytics = await provider.fetch_analytics(post["release_id"], credentials)
            _record_social_analytics(post["id"], post["user_id"], analytics)
            refreshed += 1
        except Exception:
            logger.exception("Failed to refresh analytics for post %s", post["id"])

    return {"status": "success", "refreshed": refreshed}


@router.post("/cron/execute-autoposts")
async def cron_execute_autoposts(secret: Optional[str] = None):
    # /cron/* transport stays query-param-only: this URI is registered
    # verbatim in an external Cloud Scheduler job, outside this repo.
    _sec.require_shared_secret(secret, FUNCTION_SECRET)

    # defusedxml disables external-entity/DTD resolution AND caps
    # internal-entity expansion (billion-laughs / quadratic-blowup DoS) —
    # stdlib xml.etree.ElementTree does neither by default. Combined with
    # url_safety's SSRF guard + response size cap below, this closes both
    # the "fetch an internal URL" and "feed us a malicious XML bomb" angles
    # on this cron job, which fetches whatever URL a user saved with no
    # validation at auto-post-creation time.
    import defusedxml.ElementTree as ET

    from app.core.url_safety import UnsafeURLError, safe_get

    try:
        res = supabase.table("social_auto_posts").select("*").eq("active", True).execute()
        autoposts = res.data or []
    except Exception as e:
        logger.exception("Failed to query active autoposts")
        raise HTTPException(status_code=500, detail=str(e))

    triggered_count = 0
    for auto in autoposts:
        try:
            try:
                resp = await safe_get(auto["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
            except UnsafeURLError as exc:
                logger.warning("autopost %s has an unsafe feed URL, skipping: %s", auto["id"], exc)
                continue
            xml_data = resp.content
            root = ET.fromstring(xml_data)

            # Grab the latest item
            item = root.find('.//item')
            if item is None:
                continue

            link = item.find('link').text
            title = item.find('title').text

            if link == auto.get("last_processed_url"):
                continue # No new post

            # Queue posts for each integration connected
            integrations = auto.get("integrations") or []
            post_content = f"{title}\n\nRead more: {link}"

            # Generate AI content optionally
            if auto.get("generate_content"):
                # Mock AI outlines generation using RAG or direct simple prompt
                post_content = f"🔥 New Update: {title}\n\nFind out more at: {link} #news"

            for slug in integrations:
                # Add to queue for immediate publication (now + 5 mins)
                publish_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                supabase.table("social_posts").insert({
                    "user_id": auto["user_id"],
                    "integration_slug": slug,
                    "content": post_content,
                    "publish_date": publish_time,
                    "state": "queue"
                }).execute()

            # Update last processed URL
            supabase.table("social_auto_posts").update({
                "last_processed_url": link,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", auto["id"]).execute()

            triggered_count += 1
        except Exception:
            logger.exception("Failed to execute autopost for URL %s", auto["url"])

    return {"status": "success", "triggered": triggered_count}


@router.get("/api/social/analytics")
async def get_social_analytics(user: dict[str, Any] = Depends(require_user)):
    try:
        # Fetch user's post ids
        posts_res = supabase.table("social_posts").select("id").eq("user_id", user["id"]).execute()
        post_ids = [p["id"] for p in (posts_res.data or [])]

        if not post_ids:
            return {"impressions": 0, "likes": 0, "reposts": 0, "clicks": 0}

        # Fetch analytics for these posts
        analytics_res = supabase.table("social_analytics") \
            .select("impressions, likes, reposts, clicks") \
            .in_("post_id", post_ids) \
            .execute()

        data = analytics_res.data or []
        return {
            "impressions": sum(d.get("impressions") or 0 for d in data),
            "likes": sum(d.get("likes") or 0 for d in data),
            "reposts": sum(d.get("reposts") or 0 for d in data),
            "clicks": sum(d.get("clicks") or 0 for d in data),
        }
    except Exception as e:
        logger.exception("Failed to fetch social analytics")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/social/analytics/timeseries")
async def get_social_analytics_timeseries(
    days: int = 7, user: dict[str, Any] = Depends(require_user)
):
    """Real daily rollup for the dashboard trend chart (social_analytics_daily),
    zero-filled for days with no data — replaces the old static placeholder chart."""
    days = max(1, min(days, 90))
    try:
        start_day = (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat()
        res = (
            supabase.table("social_analytics_daily")
            .select("day, impressions, likes, reposts, comments, clicks")
            .eq("user_id", user["id"])
            .gte("day", start_day)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.exception("Failed to fetch social analytics timeseries")
        raise HTTPException(status_code=500, detail=str(e))

    by_day: dict[str, dict[str, int]] = {}
    for r in rows:
        d = r["day"]
        bucket = by_day.setdefault(d, {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0})
        for k in bucket:
            bucket[k] += r.get(k) or 0

    today = datetime.now(timezone.utc).date()
    series = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        bucket = by_day.get(d, {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0})
        series.append({"date": d, **bucket})
    return {"series": series}


ALLOWED_SOCIAL_MEDIA_MIME_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "video/mp4", "video/quicktime", "video/webm",
}
MAX_SOCIAL_IMAGE_BYTES = 20 * 1024 * 1024   # 20MB — matches the composer's own label
MAX_SOCIAL_VIDEO_BYTES = 500 * 1024 * 1024  # 500MB — generous for a short social clip


async def _upload_social_media_file(user_id: str, file: UploadFile) -> dict[str, Any]:
    """Shared by the dashboard's POST /api/social/media (JWT-authed) and the
    public API's POST /api/v1/social/media (API-key-authed)."""
    try:
        mime = file.content_type or "image/png"
        if mime not in ALLOWED_SOCIAL_MEDIA_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}")

        data = await file.read()
        is_video = mime.startswith("video/")
        size_limit = MAX_SOCIAL_VIDEO_BYTES if is_video else MAX_SOCIAL_IMAGE_BYTES
        if len(data) > size_limit:
            limit_mb = size_limit // (1024 * 1024)
            raise HTTPException(status_code=400, detail=f"File too large — max {limit_mb}MB for {'video' if is_video else 'image'} uploads")

        ext = (file.filename or "file").split(".")[-1][:8] if "." in (file.filename or "") else "png"
        import uuid as _uuid
        path = f"user_{user_id}/social_{_uuid.uuid4().hex}.{ext}"

        # Upload to bucket
        supabase.storage.from_("chatty-uploads").upload(
            path, data, {"content-type": mime, "upsert": "true"}
        )
        file_url = supabase.storage.from_("chatty-uploads").get_public_url(path)

        return {
            "name": file.filename or "media_file",
            "url": file_url,
            "size": len(data),
            "type": mime,
            "media_type": "video" if is_video else "image",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Social media upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/social/media")
async def upload_social_media(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_user)
):
    return await _upload_social_media_file(user["id"], file)

@router.get("/api/social/media")
async def list_social_media(user: dict[str, Any] = Depends(require_user)):
    try:
        folder = f"user_{user['id']}"
        res = supabase.storage.from_("chatty-uploads").list(folder)
        files = []
        for item in (res or []):
            name = item.get("name")
            if name and name.startswith("social_"):
                url = supabase.storage.from_("chatty-uploads").get_public_url(f"{folder}/{name}")
                metadata = item.get("metadata") or {}
                # Supabase storage's list() usually reports the original
                # content-type; fall back to guessing from the extension for
                # older uploads (from before this field was tracked) so the
                # Media Library can still tell images and videos apart.
                mime = metadata.get("mimetype") or ("video/mp4" if name.lower().endswith((".mp4", ".mov", ".webm")) else "image/png")
                files.append({
                    "name": name,
                    "url": url,
                    "size": metadata.get("size") or 0,
                    "type": mime,
                    "media_type": "video" if mime.startswith("video/") else "image",
                    "created_at": item.get("created_at") or ""
                })
        return files
    except Exception as e:
        logger.debug("Failed to list media: %s", str(e))
        return []
