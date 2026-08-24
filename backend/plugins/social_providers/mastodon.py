"""Mastodon — self-hosted, instance-per-user. Rather than dynamic per-instance
OAuth app registration (what postiz-app does), the user generates their own
access token directly on their instance: Preferences > Development > New
Application (scopes: read, write) > copy the access token. Much simpler and
avoids needing a registered OAuth client per Mastodon server.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class MastodonProvider(SocialProvider):
    identifier = "mastodon"
    name = "Mastodon"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        instance = (form.get("instance_url") or "").strip().rstrip("/")
        token = (form.get("api_key") or "").strip()
        if not instance or not token:
            raise SocialPostError("Enter your Mastodon instance URL and access token")
        if not instance.startswith("https://"):
            instance = f"https://{instance}"
        res = await request_with_retry(
            "GET", f"{instance}/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {token}"},
        )
        if res.status_code >= 400:
            raise SocialPostError("Mastodon rejected that access token")
        me = res.json()
        return {"instance_url": instance, "access_token": token, "username": me.get("username")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        instance = credentials["instance_url"]
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        media_ids = []
        if media_urls:
            img = await request_with_retry("GET", media_urls[0])
            up = await request_with_retry(
                "POST", f"{instance}/api/v2/media", headers=headers,
                files={"file": ("media", img.content)},
            )
            if up.status_code < 400:
                media_ids = [up.json().get("id")]

        res = await request_with_retry(
            "POST", f"{instance}/api/v1/statuses", headers=headers,
            json={"status": content, "media_ids": media_ids} if media_ids else {"status": content},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"mastodon post failed ({res.status_code}): {res.text}")
        data = res.json()
        return {"status": "posted", "postId": str(data.get("id", "")), "releaseURL": data.get("url", "")}

    async def comment(self, post_id: str, content: str, credentials: dict[str, Any]) -> dict[str, Any]:
        instance = credentials["instance_url"]
        res = await request_with_retry(
            "POST", f"{instance}/api/v1/statuses",
            headers={"Authorization": f"Bearer {credentials['access_token']}"},
            json={"status": content, "in_reply_to_id": post_id},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"mastodon reply failed: {res.text}")
        return {"status": "posted", "postId": str(res.json().get("id", "")), "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        instance = credentials["instance_url"]
        res = await request_with_retry(
            "GET", f"{instance}/api/v1/statuses/{post_id}",
            headers={"Authorization": f"Bearer {credentials['access_token']}"},
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        data = res.json()
        return {
            "impressions": 0,
            "likes": data.get("favourites_count", 0),
            "reposts": data.get("reblogs_count", 0),
            "comments": data.get("replies_count", 0),
            "clicks": 0,
        }
