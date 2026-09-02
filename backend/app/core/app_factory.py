"""Builds the FastAPI app: metadata, middleware stack, and the CORS-on-error
exception handler. Route registration happens in main.py.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request as _StarletteRequest

from app.core import security as _sec
from app.core.config import ALLOWED_ORIGINS, SENTRY_DSN, SENTRY_ENV, SENTRY_TRACES_SAMPLE_RATE

logger = logging.getLogger("kin")

# NOTE (security-audit remediation): this used to describe a "Chatty API" /
# "your Chatty bots" product with support@chatty.ai contact info, a
# chatty_sk_ key prefix, and OpenAPI tags for leads/knowledge-base/bot
# management endpoints that don't exist anywhere in this codebase (grepped
# for `tags=[` across every router — only the health-check route actually
# sets a tag, "Health"). That appears to be leftover/forked scaffolding
# from a different, never-built product line rather than this one ("Kin") —
# see also the removal of the dead Widget CORS middleware and
# chatty_quota_exceeded()/get_chatty_monthly_usage() below/in main.py.
# Rewritten to describe what this API actually is and actually enforces.
_API_DESCRIPTION = """
## Kin Public API — v1

Programmatic access to your own Kin — send it a message the same way the web
chat does, or manage your connected Social accounts and posts.

### Authentication

Every endpoint below requires a **Bearer API key**, created in
**Dashboard → Developer → API Keys**:

```
Authorization: Bearer kin_sk_<your-key>
```

Keys carry `scopes` (`chat`, `read`, `write`, `admin` as a super-scope) and
an optional `allowed_ips` allowlist, both configurable per key. New keys
always get `chat`+`read`; opt into `write` when creating one if you need to
schedule posts or upload media.

### Endpoints

* `POST /api/v1/messages` — send a message to your Kin (scope: `chat`)
* `GET /api/v1/social/accounts` — list connected social accounts (`read`)
* `GET /api/v1/social/posts` — list your social posts, optional `?state=` filter (`read`)
* `POST /api/v1/social/posts` — create/schedule a post (`write`)
* `PATCH /api/v1/social/posts/{post_id}` — update a post (`write`)
* `DELETE /api/v1/social/posts/{post_id}` — delete a post (`write`)
* `POST /api/v1/social/media` — upload an image/video for a post (`write`)
* `GET /api/v1/social/analytics` — aggregate post analytics (`read`)
* `GET /api/v1/social/best-time?account_id=...` — suggest open posting slots for an account (`read`)

### Rate limits

* **60 requests / minute** per API key
* **120 requests / minute** per IP address across all `/api/v1/*` endpoints
* HTTP `429` is returned when a limit is exceeded; retry after the
  `Retry-After` header (seconds).

### Error format

All errors return JSON:

```json
{ "detail": "Human-readable error message" }
```

### Versioning

The current stable version is **v1**. Breaking changes will be released under
a new version prefix.
"""

_OPENAPI_TAGS = [
    {
        "name": "Cron",
        "description": "Internal cron/admin/worker endpoints — called by Cloud Scheduler or kin-voice-worker, protected by FUNCTION_SECRET.",
    },
    {
        "name": "Health",
        "description": "Health-check endpoint.",
    },
]


def _init_sentry() -> None:
    """No-op when SENTRY_DSN is unset, so local/dev runs need no Sentry account."""
    if not SENTRY_DSN:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENV,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
        )
        logger.info("Sentry error monitoring enabled")
    except Exception:  # noqa: BLE001
        logger.exception("Sentry init failed — continuing without it")


def create_app() -> FastAPI:
    _init_sentry()

    app = FastAPI(
        title="Kin API",
        version="1.0.0",
        description=_API_DESCRIPTION,
        contact={
            "name": "Kin Support",
            "email": "support@personaliai.com",
        },
        license_info={
            "name": "Proprietary",
        },
        openapi_tags=_OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Order matters: RequestID first (so it's available to security header middleware),
    # then SecurityHeaders, then CORS.
    app.add_middleware(_sec.SecurityHeadersMiddleware)
    app.add_middleware(_sec.RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # REMOVED (security-audit remediation): a `/api/widget/*`-scoped
    # middleware used to sit here that reflected any request Origin back as
    # Access-Control-Allow-Origin with no allowlist check — an open-CORS
    # surface, deliberately so, for a "public embed widget" product. No
    # route under /api/widget/* exists anywhere in this codebase (grepped
    # the whole tree), so the open CORS reflection was pure attack surface
    # with zero corresponding functionality — removed rather than kept
    # "just in case", consistent with removing the rest of that unbuilt
    # product's leftover scaffolding (see the Widget OpenAPI tag / Chatty
    # branding / chatty_quota_exceeded() cleanup elsewhere in this pass).
    # If a real public embed widget is built later, give it real origin
    # validation (e.g. an allowlist keyed by an embed token) rather than
    # reflecting Origin unconditionally.

    # Global exception handler — ensure CORS headers are present on 500 responses.
    # Starlette's CORSMiddleware only wraps SUCCESSFUL responses by default; when
    # an unhandled exception escapes, the response has no CORS headers and the
    # browser reports "blocked by CORS policy" hiding the real 500.
    @app.exception_handler(Exception)
    async def _global_exception_handler(request: _StarletteRequest, exc: Exception):
        # Full exception (type, message, traceback) goes to the server-side
        # log via logger.exception below — that's the only place it should
        # be visible. Previously the client-facing response also echoed
        # `type(exc).__name__: str(exc)[:300]`, leaking internal exception
        # detail (stack context, occasionally raw DB/library error text,
        # sometimes including fragments of query values) to any caller,
        # authenticated or not. Fixed during security-audit remediation —
        # the client now only ever gets a generic message plus the
        # request_id, which is enough for the caller to reference when
        # asking for help without exposing internals.
        logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        origin = request.headers.get("origin", "")
        allow_origin = origin if origin in ALLOWED_ORIGINS else (ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": _sec.get_request_id(request),
            },
            headers={
                "Access-Control-Allow-Origin": allow_origin,
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            },
        )

    return app
