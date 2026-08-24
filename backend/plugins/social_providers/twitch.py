"""Twitch — OAuth2 via the Helix API. Like Kick, Twitch has no feed/post
concept — `post()` sends a chat announcement to the broadcaster's own
channel (the closest real "post something to my audience" action Twitch's
API supports). Requires an app at https://dev.twitch.tv/console/apps. Env:
TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_REDIRECT_URI.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
SCOPES = "channel:manage:broadcast moderator:manage:announcements user:read:email"


class TwitchProvider(SocialProvider):
    identifier = "twitch"
    name = "Twitch"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("TWITCH_CLIENT_ID"),
            "redirect_uri": env_or_error("TWITCH_REDIRECT_URI"),
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
                    "client_id": env_or_error("TWITCH_CLIENT_ID"),
                    "client_secret": env_or_error("TWITCH_CLIENT_SECRET"),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri or env_or_error("TWITCH_REDIRECT_URI"),
                },
            )
            if res.status_code >= 400:
                raise SocialPostError(f"twitch token exchange failed: {res.text}")
            tokens = res.json()

            me_res = await client.get(
                "https://api.twitch.tv/helix/users",
                headers={"Authorization": f"Bearer {tokens['access_token']}", "Client-Id": env_or_error("TWITCH_CLIENT_ID")},
            )
            me_res.raise_for_status()
            user = me_res.json()["data"][0]

        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "broadcaster_id": user["id"],
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect("twitch: no refresh_token on file")
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "client_id": env_or_error("TWITCH_CLIENT_ID"),
                    "client_secret": env_or_error("TWITCH_CLIENT_SECRET"),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
            )
        if res.status_code >= 400:
            raise NeedsReconnect("twitch: refresh failed, reconnect required")
        data = res.json()
        return {**credentials, "access_token": data["access_token"], "refresh_token": data.get("refresh_token", refresh)}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        broadcaster_id = credentials["broadcaster_id"]
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Client-Id": env_or_error("TWITCH_CLIENT_ID"),
            "Content-Type": "application/json",
        }
        res = await request_with_retry(
            "POST", "https://api.twitch.tv/helix/chat/announcements",
            headers=headers,
            params={"broadcaster_id": broadcaster_id, "moderator_id": broadcaster_id},
            json={"message": content[:500]},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"twitch announcement failed ({res.status_code}): {res.text}")
        return {"status": "posted", "postId": "", "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
