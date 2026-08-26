"""Security middleware and helpers for the Chatty / Kin backend.

Provides:
  * RequestIDMiddleware  — attaches X-Request-ID to every request/response
  * SecurityHeadersMiddleware — browser-hardening headers on every response
  * IP-based rate limiting (separate from per-API-key limiting)
  * API key IP-allowlist enforcement (CIDR or exact IP)
  * API key scope enforcement (chat / read / write / admin)
  * Input sanitisation (control chars, length)
  * Fire-and-forget audit logging to chatty_api_audit_log
"""
from __future__ import annotations

import hmac
import ipaddress
import logging
import time
import uuid
from typing import Any, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("kin.security")


# ---------------------------------------------------------------------------
# Shared-secret verification (FUNCTION_SECRET-gated /cron/*, /admin/*,
# /internal/* routes)
# ---------------------------------------------------------------------------


def verify_shared_secret(provided: Optional[str], configured: str) -> bool:
    """Constant-time compare with FAIL-CLOSED semantics.

    Replaces the old `secret != FUNCTION_SECRET` pattern used across
    /cron/*, /admin/*, and /internal/* routes, which had two problems:
      1. `!=` on plain strings is not constant-time (timing side channel).
      2. `if FUNCTION_SECRET and secret != FUNCTION_SECRET` skips the check
         entirely when the env var is unset/empty — i.e. FAILS OPEN, so an
         unconfigured deploy silently has zero auth on all of these routes.
    This always denies (returns False) when `configured` is falsy, and uses
    hmac.compare_digest for the actual comparison when it isn't.
    """
    if not configured or not provided:
        return False
    return hmac.compare_digest(provided, configured)


def require_shared_secret(provided: Optional[str], configured: str) -> None:
    """Raise 403 unless `provided` matches `configured` (see
    verify_shared_secret) — the one-line gate call sites should use."""
    if not verify_shared_secret(provided, configured):
        raise HTTPException(status_code=403, detail="invalid secret")


def resolve_gated_secret(request: Request, query_secret: Optional[str]) -> Optional[str]:
    """Preferred transport for /admin/* and /internal/* routes: an
    `Authorization: Bearer <secret>` header. Falls back to the legacy
    `secret` query-string param for backward compatibility (query strings
    end up in access logs / proxy logs / browser history, so the header
    path should be used by any caller that can be updated to use it).
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    return query_secret

# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Echo or generate an X-Request-ID on every request/response."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["x-request-id"] = req_id
        return response


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add browser-hardening response headers to every response.

    Safe to apply globally — headers are set with setdefault so they don't
    override any already-set values (e.g. CORS headers from widget middleware).
    """

    _HEADERS = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "x-permitted-cross-domain-policies": "none",
        # Cloud Run is always HTTPS so we can safely set HSTS
        "strict-transport-security": "max-age=31536000; includeSubDomains; preload",
        # The API only serves JSON — block everything else
        "content-security-policy": "default-src 'none'",
        "permissions-policy": "geolocation=(), camera=(), microphone=()",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in self._HEADERS.items():
            response.headers.setdefault(name, value)
        return response


# ---------------------------------------------------------------------------
# IP-based rate limiter
# ---------------------------------------------------------------------------

# KNOWN LIMITATION: this is a plain in-process dict, not the Redis-backed
# store the UPSTASH_REDIS_REST_URL/TOKEN env vars were provisioned for (see
# env.yaml comment) — it resets on every restart/deploy and is independent
# per Cloud Run instance, so real allowed throughput scales with instance
# count. Good enough to stop a single runaway client from one instance;
# not a substitute for a real distributed limiter under autoscaling. Wiring
# up Upstash here is a reasonable follow-up but was out of scope for this
# fix (it adds a new runtime dependency on the Redis REST API on every
# request path, which deserves its own review rather than a drive-by change).
_ip_state: dict[str, list[float]] = {}


def ip_rate_limited(bucket: str, limit: int, window: int) -> bool:
    """Sliding-window check. Returns True when the bucket has hit the limit."""
    now = time.time()
    hits = [t for t in _ip_state.get(bucket, []) if now - t < window]
    if len(hits) >= limit:
        _ip_state[bucket] = hits
        return True
    hits.append(now)
    _ip_state[bucket] = hits
    return False


def check_ip_rate(request: Request, limit: int = 120, window: int = 60) -> None:
    """Raise 429 when the request IP exceeds the given rate on this path."""
    ip = _client_ip(request)
    bucket = f"ip:{ip}:{request.url.path}"
    if ip_rate_limited(bucket, limit=limit, window=window):
        raise HTTPException(
            status_code=429,
            detail="Too many requests from this IP address. Please slow down.",
            headers={"Retry-After": str(window)},
        )


def check_key_rate(key_id: str, limit: int = 60, window: int = 60) -> None:
    """Raise 429 when a single API key exceeds the given rate, independent of
    IP (a key used from many IPs, or many keys from one IP, are both capped).
    Same in-process sliding-window mechanism as check_ip_rate — see the
    "known limitation" note on _ip_state below for the multi-instance caveat.
    """
    bucket = f"key:{key_id}"
    if ip_rate_limited(bucket, limit=limit, window=window):
        raise HTTPException(
            status_code=429,
            detail="Too many requests for this API key. Please slow down.",
            headers={"Retry-After": str(window)},
        )


# ---------------------------------------------------------------------------
# IP allowlist enforcement
# ---------------------------------------------------------------------------


def check_ip_allowlist(key_row: dict[str, Any], request: Request) -> None:
    """If the key has an IP allowlist, verify the request IP is in it.

    Each entry in allowed_ips may be an exact IPv4/IPv6 address or a CIDR
    range (e.g. "10.0.0.0/8", "2001:db8::/32").
    """
    allowed: list[str] = key_row.get("allowed_ips") or []
    if not allowed:
        return
    client_ip = _client_ip(request)
    try:
        parsed_client = ipaddress.ip_address(client_ip)
    except ValueError:
        # Unparseable IP — deny by default
        raise HTTPException(
            status_code=403,
            detail="Could not determine request IP address for allowlist check.",
        )
    for entry in allowed:
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if parsed_client in ipaddress.ip_network(entry, strict=False):
                    return
            else:
                if parsed_client == ipaddress.ip_address(entry):
                    return
        except ValueError:
            logger.warning("Invalid entry in allowed_ips: %r", entry)
    raise HTTPException(
        status_code=403,
        detail=(
            f"IP address {client_ip!r} is not permitted for this API key. "
            "Update the allowlist in your Chatty dashboard → API Keys."
        ),
    )


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------

# Available scopes and what they grant:
#   chat   — call /api/v1/chat (send messages to the bot)
#   read   — read leads, conversations, usage, bot metadata, knowledge sources
#   write  — add/delete knowledge sources, manage conversation sessions
#   admin  — all of the above (super-scope; granted to dashboard-created keys)
VALID_SCOPES = {"chat", "read", "write", "admin"}
_DEFAULT_SCOPES = ["chat", "read"]


def check_scope(key_row: dict[str, Any], required: str) -> None:
    """Raise 403 when the API key does not have the required scope.

    The 'admin' scope is a super-scope that satisfies any requirement.
    """
    scopes: list[str] = key_row.get("scopes") or _DEFAULT_SCOPES
    if "admin" in scopes or required in scopes:
        return
    raise HTTPException(
        status_code=403,
        detail=(
            f"This API key is missing the '{required}' scope. "
            f"Current scopes: {scopes}. "
            "Update your key's scopes in the Chatty dashboard → API Keys."
        ),
    )


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------

# Control characters that are never valid in chat text
# (allow tab \t=9, newline \n=10, carriage return \r=13)
_CTRL = frozenset(range(32)) - {9, 10, 13}


def sanitize_text(text: str, max_len: int = 4000) -> str:
    """Strip C0 control characters and truncate to max_len."""
    return "".join(ch for ch in text if ord(ch) not in _CTRL)[:max_len]


# ---------------------------------------------------------------------------
# Audit logging (fire-and-forget, non-blocking)
# ---------------------------------------------------------------------------


def log_api_access(
    supabase_client,
    *,
    key_id: str,
    user_id: Optional[str],
    endpoint: str,
    method: str,
    client_ip: str,
    request_id: str,
    status_code: int = 200,
    duration_ms: int = 0,
) -> None:
    """Write one row to kin_api_audit_log (see the
    20260826000000_public_api_scopes_and_audit.sql migration). Failures are
    swallowed — never let audit logging break a live request.

    NOTE: this previously wrote to a table named chatty_api_audit_log and
    took a `bot_id` kwarg — that table was never created anywhere in this
    codebase's migrations (a leftover from an unbuilt "Chatty" widget
    product; see app_factory.py's Widget-tag cleanup), so every call to this
    function would have failed. It's repointed at the real kin_api_keys /
    Kin-user model (user_id, not bot_id) that app/routers/chat.py actually
    uses for the public API.
    """
    try:
        supabase_client.table("kin_api_audit_log").insert({
            "key_id": key_id,
            "user_id": user_id,
            "endpoint": endpoint,
            "method": method,
            "client_ip": client_ip,
            "request_id": request_id,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }).execute()
    except Exception:
        logger.warning("Failed to write audit log", exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    """Best-effort real client IP behind Cloud Run.

    X-Forwarded-For can contain multiple hops: any hops the CLIENT sent
    themselves (spoofable — e.g. "X-Forwarded-For: 1.2.3.4" set by an
    attacker) come first, and Cloud Run's own front end APPENDS the real
    connecting-socket IP as the LAST entry. Previously this took the FIRST
    entry, which let any caller spoof their apparent IP and bypass both the
    IP rate limiter and the API-key IP allowlist just by setting the header
    themselves. Take the last entry instead — the one hop we didn't let the
    client write.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def client_ip(request: Request) -> str:
    """Public wrapper around _client_ip, for callers outside this module
    (e.g. audit logging in app/routers/chat.py) that need the same
    spoof-resistant IP resolution used by the rate limiter/allowlist."""
    return _client_ip(request)
