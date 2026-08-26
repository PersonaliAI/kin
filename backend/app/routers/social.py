from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from plugins import social_providers as sp

from app.core import security as _sec
from app.core.clients import supabase
from app.core.config import FUNCTION_SECRET, MODEL_NAME
from app.core.deps import require_user
from app.core.llm import complete as llm_complete
from app.schemas.social import (
    SocialAutoPostCreate,
    SocialGenerateRequest,
    SocialPostCreate,
    SocialPostUpdate,
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
    res = (
        supabase.table("social_webhooks")
        .select("id, url, active, created_at")
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    return res.data or None


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
# AI content generation for the composer's "AI Copilot" tab — reuses the
# same Gemini client as the rest of Kin (genai_client / MODEL_NAME).
# ---------------------------------------------------------------------------


@router.post("/api/social/generate")
async def social_generate_content(body: SocialGenerateRequest, user: dict[str, Any] = Depends(require_user)):
    topic = body.prompt.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="prompt is required")
    if body.url:
        topic = f"{topic}\n\nReference URL: {body.url}"

    if body.kind == "outlines":
        instruction = (
            f"Write 3 short, distinct social media post drafts about the following, in a {body.tone} tone. "
            "Each should be 1-3 sentences, ready to post as-is. Return each draft separated by a line "
            "containing only '---', with no numbering or extra commentary.\n\n" + topic
        )
    else:
        instruction = (
            f"Write a single, polished social media post about the following, in a {body.tone} tone. "
            "Return only the post text, no commentary.\n\n" + topic
        )

    try:
        response = await llm_complete(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": instruction}],
            temperature=0.9,
            max_tokens=500,
            feature="social_post",
            user_id=user["id"],
        )
        text = (response.text or "").strip()
    except Exception as e:
        logger.exception("social AI generation failed")
        raise HTTPException(status_code=502, detail=str(e))

    if body.kind == "outlines":
        outlines = [o.strip() for o in text.split("---") if o.strip()]
        return {"outlines": outlines or [text]}
    return {"content": text}


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


@router.post("/api/social/posts")
async def create_social_post(body: SocialPostCreate, user: dict[str, Any] = Depends(require_user)):
    try:
        account_ids = list(body.social_account_ids or [])

        # Legacy fallback for any caller still sending a bare integration_slug
        # (no social_account_ids): resolve it to that user's most-recently
        # connected account of that platform.
        if not account_ids and body.integration_slug:
            fallback = (
                supabase.table("social_accounts")
                .select("id")
                .eq("user_id", user["id"])
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
            .eq("user_id", user["id"])
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
                "user_id": user["id"],
                "integration_slug": slug_by_id[account_id],
                "social_account_id": account_id,
                "group_id": group_id,
                "content": overrides.get(account_id, body.content),
                "publish_date": body.publish_date,
                "state": body.state,
                "image_url": body.image_url,
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
                    "user_id": user["id"],
                    "integration_slug": slug_by_id[account_id],
                    "social_account_id": account_id,
                    "group_id": group_id,
                    "content": overrides.get(account_id, body.content),
                    "publish_date": _shift_interval(base_date, body.repeat_interval, i).isoformat(),
                    "state": body.state,
                    "image_url": body.image_url,
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


@router.post("/api/social/media")
async def upload_social_media(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_user)
):
    try:
        data = await file.read()
        mime = file.content_type or "image/png"
        ext = (file.filename or "file").split(".")[-1][:8] if "." in (file.filename or "") else "png"
        import uuid as _uuid
        path = f"user_{user['id']}/social_{_uuid.uuid4().hex}.{ext}"

        # Upload to bucket
        supabase.storage.from_("chatty-uploads").upload(
            path, data, {"content-type": mime, "upsert": "true"}
        )
        file_url = supabase.storage.from_("chatty-uploads").get_public_url(path)

        return {
            "name": file.filename or "media_file",
            "url": file_url,
            "size": len(data),
            "type": mime
        }
    except Exception as e:
        logger.exception("Social media upload failed")
        raise HTTPException(status_code=500, detail=str(e))

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
                files.append({
                    "name": name,
                    "url": url,
                    "size": item.get("metadata", {}).get("size") or 0,
                    "created_at": item.get("created_at") or ""
                })
        return files
    except Exception as e:
        logger.debug("Failed to list media: %s", str(e))
        return []
