"""Medium — Integration Token (no OAuth). Note: Medium stopped issuing new
integration tokens to most accounts several years ago; this only works for
accounts that already have one (Settings > Integration tokens). Kept for
parity with existing accounts / postiz-app's own medium.provider.ts.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class MediumProvider(SocialProvider):
    identifier = "medium"
    name = "Medium"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        token = (form.get("api_key") or "").strip()
        if not token:
            raise SocialPostError("Enter your Medium integration token")
        res = await request_with_retry(
            "GET", "https://api.medium.com/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
        if res.status_code >= 400:
            raise SocialPostError("Medium rejected that integration token")
        me = res.json().get("data", {})
        return {"api_key": token, "user_id": me.get("id"), "username": me.get("username")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        title, _, body = content.partition("\n")
        title = title[:250] or "New post"
        markdown = body or content
        if media_urls:
            markdown = f"![]({media_urls[0]})\n\n{markdown}"
        publish_status = settings.get("publish_status")
        payload: dict[str, Any] = {
            "title": title,
            "contentFormat": "markdown",
            "content": markdown,
            "publishStatus": publish_status if publish_status in ("public", "draft", "unlisted") else "public",
        }
        tags = [t.strip() for t in (settings.get("tags") or []) if t.strip()]
        if tags:
            payload["tags"] = tags[:5]
        if settings.get("canonical_url"):
            payload["canonicalUrl"] = settings["canonical_url"]
        res = await request_with_retry(
            "POST",
            f"https://api.medium.com/v1/users/{credentials['user_id']}/posts",
            headers={"Authorization": f"Bearer {credentials['api_key']}", "Content-Type": "application/json"},
            json=payload,
        )
        if res.status_code >= 400:
            raise SocialPostError(f"medium post failed ({res.status_code}): {res.text}")
        data = res.json().get("data", {})
        return {"status": "posted", "postId": data.get("id", ""), "releaseURL": data.get("url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Medium's public API has no post-level stats endpoint.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
