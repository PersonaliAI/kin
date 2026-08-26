from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.clients import supabase
from app.core.config import FRONTEND_URL
from app.core.deps import require_user
from app.schemas.mcp import McpCreate

from main import _oauth_state_secret

logger = logging.getLogger("kin")

router = APIRouter()

# mcp_servers columns that must never leave this API in plaintext — same
# problem class as voice_agents.py's BYOK keys, just not masked here yet.
# `select("*")` was returning every one of these straight to the frontend
# on GET /api/mcp and the POST /api/mcp response (create_mcp_server returns
# the just-upserted row, which already contains whatever the caller sent in
# body.oauth_client_secret / body.headers). The frontend TypeScript type
# for an MCP server already models a `has_oauth_client_secret`-shaped
# field, expecting the backend to mask — this is that fix, applied to all
# of the sensitive columns actually on this table, not just
# oauth_client_secret.
_MCP_SECRET_FIELDS = (
    "oauth_client_secret",
    "oauth_access_token",
    "oauth_refresh_token",
    "oauth_code_verifier",
)


def _mask_mcp_server(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for field in _MCP_SECRET_FIELDS:
        row[f"has_{field}"] = bool(row.get(field))
        row.pop(field, None)
    # `headers` is a free-form dict the user can put anything in (often an
    # Authorization bearer token for the target MCP server) — redact values,
    # keep keys, so the UI can still show which header names are configured.
    headers = row.get("headers")
    if isinstance(headers, dict) and headers:
        row["headers"] = {k: "••••••••" for k in headers}
    return row


@router.get("/api/mcp")
async def get_mcp_servers(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("mcp_servers").select("*").eq("user_id", user["id"]).execute()
        return [_mask_mcp_server(row) for row in (res.data or [])]
    except Exception as e:
        logger.exception("Failed to query MCP servers")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp")
async def create_mcp_server(request: Request, body: McpCreate, user: dict[str, Any] = Depends(require_user)):
    import re
    if not re.match(r"^[a-zA-Z0-9_]+$", body.name):
        raise HTTPException(
            status_code=400,
            detail="MCP server name must contain only alphanumeric characters and underscores."
        )

    from app.core.url_safety import UnsafeURLError, assert_safe_url
    try:
        assert_safe_url(body.url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or disallowed MCP server url: {exc}")

    from plugins import mcp_client

    # Try to discover OAuth endpoints
    discovered = await mcp_client.discover_mcp_oauth(body.url, body.headers)
    is_oauth = False
    auth_url = body.oauth_auth_url
    token_url = body.oauth_token_url
    client_id = body.oauth_client_id
    client_secret = body.oauth_client_secret

    if discovered:
        is_oauth = True
        auth_url = auth_url or discovered.get("authorization_endpoint")
        token_url = token_url or discovered.get("token_endpoint")

        # If DCR registration endpoint is exposed, perform Dynamic Client Registration
        reg_endpoint = discovered.get("registration_endpoint")
        if reg_endpoint and not client_id:
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            redirect_uri = f"{scheme}://{request.url.netloc}/auth/mcp/callback"
            try:
                registered = await mcp_client.register_mcp_oauth_client(reg_endpoint, redirect_uri)
                if registered:
                    client_id = registered.get("client_id")
                    client_secret = registered.get("client_secret")
                    logger.info(f"Dynamically registered MCP OAuth client: {client_id} for redirect: {redirect_uri}")
            except Exception:
                logger.exception("Dynamic Client Registration failed")

        if not client_id:
            raise HTTPException(
                status_code=400,
                detail="This MCP server requires OAuth but does not support Dynamic Client Registration. "
                       "Please click 'Show Advanced OAuth Options' and configure your Client ID manually."
            )
    elif body.oauth_client_id or body.oauth_auth_url:
        is_oauth = True

    tools = []
    flow_status = "none"

    if is_oauth:
        flow_status = "awaiting_authorization"
    else:
        try:
            tools = await mcp_client.list_remote_tools(body.url, body.headers)
        except Exception as e:
            logger.exception("Failed to contact remote MCP server")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to MCP server: {e}"
            )

    try:
        data = {
            "user_id": user["id"],
            "name": body.name,
            "url": body.url,
            "headers": body.headers or {},
            "tools": tools,
            "oauth_flow_status": flow_status,
            "oauth_client_id": client_id,
            "oauth_client_secret": client_secret,
            "oauth_auth_url": auth_url,
            "oauth_token_url": token_url,
            "oauth_scopes": body.oauth_scopes,
            "updated_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("mcp_servers").upsert(data, on_conflict="user_id,name").execute()
        if res.data:
            return _mask_mcp_server(res.data[0])
        raise HTTPException(status_code=500, detail="Failed to save MCP server")
    except Exception as e:
        logger.exception("Failed to save MCP server")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp/{mcp_id}/test")
async def test_mcp_connection(mcp_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("mcp_servers").select("*").eq("id", mcp_id).eq("user_id", user["id"]).execute()
        server = res.data[0] if res.data else None
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        from plugins import mcp_client
        from app.core.url_safety import UnsafeURLError, assert_safe_url

        # Check OAuth status
        if server.get("oauth_flow_status") == "awaiting_authorization":
            raise HTTPException(
                status_code=400,
                detail="MCP server is awaiting authorization. Please authorize the server first."
            )

        # Re-validate at connect time (create_mcp_server already validated on
        # save, but DNS can change between save and test).
        try:
            assert_safe_url(server["url"])
        except UnsafeURLError as exc:
            raise HTTPException(status_code=400, detail=f"MCP server url is no longer safe to connect to: {exc}")

        headers = await mcp_client.get_mcp_headers(server)
        tools = await mcp_client.list_remote_tools(server["url"], headers)

        # Cache tools
        supabase.table("mcp_servers").update({
            "tools": tools,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", mcp_id).execute()

        return {"status": "success", "tools": tools}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("MCP server test failed")
        raise HTTPException(status_code=400, detail=f"Connection test failed: {e}")


@router.post("/api/mcp/{mcp_id}/oauth/start")
async def mcp_oauth_start(mcp_id: str, redirect_uri: str, user: dict[str, Any] = Depends(require_user)):
    res = supabase.table("mcp_servers").select("*").eq("id", mcp_id).eq("user_id", user["id"]).execute()
    server = res.data[0] if res.data else None
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    auth_url = server.get("oauth_auth_url")
    client_id = server.get("oauth_client_id")
    if not auth_url or not client_id:
        raise HTTPException(
            status_code=400,
            detail="MCP server is not configured for OAuth (missing Authorization URL or Client ID)."
        )

    import secrets
    import hashlib
    import base64

    # Generate PKCE verifier and challenge
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().replace("=", "").replace("+", "-").replace("/", "_")

    # Save the verifier in the DB
    supabase.table("mcp_servers").update({
        "oauth_code_verifier": verifier
    }).eq("id", mcp_id).execute()

    # Generate the state JWT containing user_id and mcp_id
    import time
    import jwt
    state_payload = {
        "sub": user["id"],
        "mcp_id": mcp_id,
        "exp": int(time.time()) + 900
    }
    # Signed with the same decoupled OAuth-state secret as main.py's
    # _mint_state (falls back to FUNCTION_SECRET with a startup warning if
    # OAUTH_STATE_SECRET isn't set) — this used to sign directly with
    # FUNCTION_SECRET, duplicating the coupling issue fixed there.
    state = jwt.encode(state_payload, _oauth_state_secret(), algorithm="HS256")

    scopes = server.get("oauth_scopes") or ""
    import urllib.parse
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }
    if scopes:
        params["scope"] = scopes

    auth_redirect_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return {"url": auth_redirect_url}


@router.get("/auth/mcp/callback")
async def mcp_oauth_callback(request: Request, code: str, state: str):
    import jwt
    import time
    import json
    from datetime import datetime, timezone, timedelta

    try:
        payload = jwt.decode(state, _oauth_state_secret(), algorithms=["HS256"])
        user_id = payload["sub"]
        mcp_id = payload["mcp_id"]
    except jwt.PyJWTError:
        return RedirectResponse(f"{FRONTEND_URL}/dashboard/mcp?oauth=error&detail=invalid_state")

    try:
        res = supabase.table("mcp_servers").select("*").eq("id", mcp_id).eq("user_id", user_id).execute()
        server = res.data[0] if res.data else None
        if not server:
            return RedirectResponse(f"{FRONTEND_URL}/dashboard/mcp?oauth=error&detail=server_not_found")

        token_url = server.get("oauth_token_url")
        client_id = server.get("oauth_client_id")
        verifier = server.get("oauth_code_verifier")

        # Build redirect_uri dynamically based on the request's origin host
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        redirect_uri = f"{scheme}://{request.url.netloc}/auth/mcp/callback"

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier
        }
        client_secret = server.get("oauth_client_secret")
        if client_secret:
            payload["client_secret"] = client_secret

        async with httpx.AsyncClient(timeout=15.0) as client:
            token_res = await client.post(token_url, data=payload)
            if token_res.status_code != 200:
                logger.error(
                    "MCP OAuth token exchange failed: Status %d, Body %s",
                    token_res.status_code, token_res.text
                )
                return RedirectResponse(
                    f"{FRONTEND_URL}/dashboard/mcp?oauth=error&detail=token_exchange_failed"
                )

            tokens = token_res.json()
            access = tokens["access_token"]
            refresh = tokens.get("refresh_token")
            expires_in = int(tokens.get("expires_in", 3600))

            # Save token to database
            update_data = {
                "oauth_access_token": access,
                "oauth_refresh_token": refresh,
                "oauth_token_expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                ).isoformat(),
                "oauth_flow_status": "authorized"
            }
            supabase.table("mcp_servers").update(update_data).eq("id", mcp_id).execute()

            # Connect to MCP server using newly obtained access token and retrieve its tools list
            from plugins import mcp_client
            headers = {"Authorization": f"Bearer {access}"}
            custom_headers = server.get("headers") or {}
            if isinstance(custom_headers, str):
                try:
                    custom_headers = json.loads(custom_headers)
                except Exception:
                    custom_headers = {}
            headers.update(custom_headers)

            try:
                tools = await mcp_client.list_remote_tools(server["url"], headers)
                supabase.table("mcp_servers").update({
                    "tools": tools,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", mcp_id).execute()
            except Exception:
                logger.exception("Failed to fetch tools after successful OAuth for MCP server %s", mcp_id)

            return RedirectResponse(f"{FRONTEND_URL}/dashboard/mcp?mcp_id={mcp_id}&oauth=success")

    except Exception as e:
        logger.exception("MCP OAuth callback failed")
        return RedirectResponse(f"{FRONTEND_URL}/dashboard/mcp?oauth=error&detail={e}")


@router.delete("/api/mcp/{mcp_id}")
async def delete_mcp_server(mcp_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("mcp_servers").delete().eq("id", mcp_id).eq("user_id", user["id"]).execute()
        return {"status": "deleted"}
    except Exception as e:
        logger.exception("Failed to delete MCP server")
        raise HTTPException(status_code=500, detail=str(e))
