"""Kick — OAuth2 via Kick's public API (https://docs.kick.com). Kick is a
livestreaming platform, not a feed platform — there's no "create a post"
concept, so `post()` is mapped to the closest real equivalent: updating the
channel's stream title, which is what shows up as the channel's public
"post" to followers. Env: KICK_CLIENT_ID, KICK_CLIENT_SECRET,
KICK_REDIRECT_URI.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://id.kick.com/oauth/authorize"
TOKEN_URL = "https://id.kick.com/oauth/token"
SCOPES = "user:read channel:read channel:write"


class KickProvider(SocialProvider):
    identifier = "kick"
    name = "Kick"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        from urllib.parse import urlencode
        params = {
            "client_id": env_or_error("KICK_CLIENT_ID"),
            "redirect_uri": env_or_error("KICK_REDIRECT_URI"),
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": env_or_error("KICK_CLIENT_ID"),
                    "client_secret": env_or_error("KICK_CLIENT_SECRET"),
                    "redirect_uri": redirect_uri or env_or_error("KICK_REDIRECT_URI"),
                    "code": code,
                },
            )
        if res.status_code >= 400:
            raise SocialPostError(f"kick token exchange failed: {res.text}")
        data = res.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect("kick: no refresh_token on file")
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": env_or_error("KICK_CLIENT_ID"),
                    "client_secret": env_or_error("KICK_CLIENT_SECRET"),
                    "refresh_token": refresh,
                },
            )
        if res.status_code >= 400:
            raise NeedsReconnect("kick: refresh failed, reconnect required")
        data = res.json()
        return {**credentials, "access_token": data["access_token"], "refresh_token": data.get("refresh_token", refresh)}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {credentials['access_token']}", "Content-Type": "application/json"}
        res = await request_with_retry(
            "PATCH", "https://api.kick.com/public/v1/channels",
            headers=headers, json={"stream_title": content[:140]},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"kick channel update failed ({res.status_code}): {res.text}")
        return {"status": "posted", "postId": "", "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
