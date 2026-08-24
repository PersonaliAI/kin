"""VK (VKontakte) — OAuth2. Requires a "Standalone/VK Mini App" at
https://dev.vk.com/en/admin/apps-list. Env: VK_CLIENT_ID, VK_CLIENT_SECRET,
VK_REDIRECT_URI. Posts to the user's own wall.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://oauth.vk.com/authorize"
TOKEN_URL = "https://oauth.vk.com/access_token"
API_VERSION = "5.199"


class VKProvider(SocialProvider):
    identifier = "vk"
    name = "VK"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("VK_CLIENT_ID"),
            "redirect_uri": env_or_error("VK_REDIRECT_URI"),
            "scope": "wall,photos,offline",
            "response_type": "code",
            "state": state,
            "v": API_VERSION,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                TOKEN_URL,
                params={
                    "client_id": env_or_error("VK_CLIENT_ID"),
                    "client_secret": env_or_error("VK_CLIENT_SECRET"),
                    "redirect_uri": redirect_uri or env_or_error("VK_REDIRECT_URI"),
                    "code": code,
                },
            )
        if res.status_code >= 400:
            raise SocialPostError(f"vk token exchange failed: {res.text}")
        data = res.json()
        return {"access_token": data["access_token"], "user_id": data.get("user_id")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        params = {
            "message": content,
            "access_token": credentials["access_token"],
            "v": API_VERSION,
        }
        res = await request_with_retry("POST", "https://api.vk.com/method/wall.post", data=params)
        data = res.json()
        if "error" in data:
            raise SocialPostError(f"vk post failed: {data['error']}")
        post_id = data.get("response", {}).get("post_id", "")
        user_id = credentials.get("user_id", "")
        url = f"https://vk.com/wall{user_id}_{post_id}" if post_id else ""
        return {"status": "posted", "postId": str(post_id), "releaseURL": url}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        user_id = credentials.get("user_id", "")
        res = await request_with_retry(
            "GET", "https://api.vk.com/method/wall.getById",
            params={"posts": f"{user_id}_{post_id}", "access_token": credentials["access_token"], "v": API_VERSION},
        )
        data = res.json().get("response", [])
        if not data:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        p = data[0]
        return {
            "impressions": p.get("views", {}).get("count", 0),
            "likes": p.get("likes", {}).get("count", 0),
            "reposts": p.get("reposts", {}).get("count", 0),
            "comments": p.get("comments", {}).get("count", 0),
            "clicks": 0,
        }
