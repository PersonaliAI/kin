"""Whop — API key (no OAuth), posts to a Whop community's forum feed.

LOW CONFIDENCE: Whop's public API for creating forum posts is less
standardized/documented than the other providers in this file — verify the
endpoint shape against https://dev.whop.com/api-reference before relying on
this in production. Connect (API key validation) is solid; post() follows
Whop's documented v2 REST conventions (Bearer token, JSON) but the exact
forum-post endpoint may need adjusting once tested against a real app.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry

API_BASE = "https://api.whop.com/api/v2"


class WhopProvider(SocialProvider):
    identifier = "whop"
    name = "Whop"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        api_key = (form.get("api_key") or "").strip()
        forum_id = (form.get("forum_id") or "").strip()
        if not api_key or not forum_id:
            raise SocialPostError("Enter your Whop API key and forum experience id")
        res = await request_with_retry(
            "GET", f"{API_BASE}/me", headers={"Authorization": f"Bearer {api_key}"}
        )
        if res.status_code >= 400:
            raise SocialPostError("Whop rejected that API key")
        return {"api_key": api_key, "forum_id": forum_id}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {credentials['api_key']}", "Content-Type": "application/json"}
        body: dict[str, Any] = {"content": content}
        if media_urls:
            body["attachments"] = [{"url": media_urls[0]}]
        res = await request_with_retry(
            "POST", f"{API_BASE}/forums/{credentials['forum_id']}/posts", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise SocialPostError(f"whop post failed ({res.status_code}): {res.text}")
        data = res.json()
        return {"status": "posted", "postId": str(data.get("id", "")), "releaseURL": data.get("url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
