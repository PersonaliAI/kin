"""TikTok — OAuth2 via TikTok's Content Posting API v2. Requires an app at
https://developers.tiktok.com/apps with the "Content Posting API" product
(and PULL_FROM_URL requires TikTok to verify Kin's media storage domain).
Env: TIKTOK_CLIENT_ID (TikTok calls this "client_key"), TIKTOK_CLIENT_SECRET,
TIKTOK_REDIRECT_URI.

Posting is asynchronous on TikTok's side (publish is queued, not
immediate) — post() returns the publish_id; the actual video isn't
guaranteed live yet when this returns.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = "user.info.basic,video.publish,video.upload"


class TikTokProvider(SocialProvider):
    identifier = "tiktok"
    name = "TikTok"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_key": env_or_error("TIKTOK_CLIENT_ID"),
            "redirect_uri": env_or_error("TIKTOK_REDIRECT_URI"),
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "client_key": env_or_error("TIKTOK_CLIENT_ID"),
                    "client_secret": env_or_error("TIKTOK_CLIENT_SECRET"),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri or env_or_error("TIKTOK_REDIRECT_URI"),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if res.status_code >= 400:
            raise SocialPostError(f"tiktok token exchange failed: {res.text}")
        data = res.json()
        if "error" in data and data["error"]:
            raise SocialPostError(f"tiktok token exchange failed: {data}")
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "open_id": data.get("open_id"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect("tiktok: no refresh_token on file")
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "client_key": env_or_error("TIKTOK_CLIENT_ID"),
                    "client_secret": env_or_error("TIKTOK_CLIENT_SECRET"),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
            )
        if res.status_code >= 400:
            raise NeedsReconnect("tiktok: refresh failed, reconnect required")
        data = res.json()
        return {
            **credentials,
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh),
            "expires_in": data.get("expires_in"),
        }

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not media_urls:
            raise SocialPostError("tiktok: a video is required")
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }
        settings = settings or {}
        privacy_map = {
            "everyone": "PUBLIC_TO_EVERYONE",
            "friends": "MUTUAL_FOLLOW_FRIENDS",
            "self": "SELF_ONLY",
        }
        body = {
            "post_info": {
                "title": content[:150],
                "privacy_level": privacy_map.get(settings.get("privacy", "self"), "SELF_ONLY"),
                "disable_comment": not settings.get("allow_comments", True),
                "disable_duet": not settings.get("allow_duets", True),
                "disable_stitch": not settings.get("allow_stitch", True),
            },
            "source_info": {"source": "PULL_FROM_URL", "video_url": media_urls[0]},
        }
        res = await request_with_retry(
            "POST",
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=headers, json=body,
        )
        if res.status_code >= 400:
            raise SocialPostError(f"tiktok publish failed ({res.status_code}): {res.text}")
        data = res.json().get("data", {})
        publish_id = data.get("publish_id", "")
        return {"status": "posted", "postId": publish_id, "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # video.list scope (separate approval) is needed to read view/like
        # counts for a specific video by id — not requested by default here.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
