"""Dev.to — API key (no OAuth). User pastes a key generated at
https://dev.to/settings/extensions ("DEV Community API Keys").
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class DevToProvider(SocialProvider):
    identifier = "dev_to"
    name = "Dev.to"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        api_key = (form.get("api_key") or "").strip()
        if not api_key:
            raise SocialPostError("Enter your Dev.to API key")
        res = await request_with_retry("GET", "https://dev.to/api/users/me", headers={"api-key": api_key})
        if res.status_code >= 400:
            raise SocialPostError("Dev.to rejected that API key")
        me = res.json()
        return {"api_key": api_key, "username": me.get("username")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        title, _, body = content.partition("\n")
        title = title[:250] or "New post"
        markdown = body or content
        if media_urls:
            markdown = f"![]({media_urls[0]})\n\n{markdown}"
        res = await request_with_retry(
            "POST",
            "https://dev.to/api/articles",
            headers={"api-key": credentials["api_key"], "Content-Type": "application/json"},
            json={"article": {"title": title, "body_markdown": markdown, "published": True}},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"dev.to post failed ({res.status_code}): {res.text}")
        data = res.json()
        return {"status": "posted", "postId": str(data.get("id", "")), "releaseURL": data.get("url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET", f"https://dev.to/api/articles/{post_id}", headers={"api-key": credentials["api_key"]}
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        data = res.json()
        return {
            "impressions": data.get("page_views_count", 0),
            "likes": data.get("public_reactions_count", 0),
            "reposts": 0,
            "comments": data.get("comments_count", 0),
            "clicks": 0,
        }
