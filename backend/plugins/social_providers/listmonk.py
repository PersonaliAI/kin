"""Listmonk — self-hosted newsletter tool, REST API with HTTP Basic auth (no
OAuth). Requires the user's own Listmonk instance domain, an API user, and
an API token (Listmonk Admin > Settings > API). "Posting" here means
creating and immediately sending a one-off campaign to a chosen list.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class ListmonkProvider(SocialProvider):
    identifier = "listmonk"
    name = "Listmonk"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        domain = (form.get("domain") or "").strip().rstrip("/")
        api_user = (form.get("api_user") or "").strip()
        api_key = (form.get("api_key") or "").strip()
        list_id = form.get("list_id")
        if not domain or not api_user or not api_key or not list_id:
            raise SocialPostError("Enter your Listmonk domain, API user, API key, and list id")
        res = await request_with_retry(
            "GET", f"{domain}/api/lists", auth=(api_user, api_key)
        )
        if res.status_code >= 400:
            raise SocialPostError("Listmonk rejected those credentials")
        return {"domain": domain, "api_user": api_user, "api_key": api_key, "list_id": int(list_id)}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        domain = credentials["domain"]
        auth = (credentials["api_user"], credentials["api_key"])
        title, _, body = content.partition("\n")
        subject = title[:200] or "New campaign"
        html = (body or content).replace("\n", "<br>")
        if media_urls:
            html = f'<img src="{media_urls[0]}" /><br>{html}'
        list_id = settings.get("list_id") or credentials["list_id"]

        create_res = await request_with_retry(
            "POST", f"{domain}/api/campaigns", auth=auth,
            json={
                "name": subject,
                "subject": subject,
                "lists": [list_id],
                "type": "regular",
                "content_type": "html",
                "body": html,
            },
        )
        if create_res.status_code >= 400:
            raise SocialPostError(f"listmonk campaign create failed: {create_res.text}")
        campaign_id = create_res.json().get("data", {}).get("id")

        send_res = await request_with_retry(
            "PUT", f"{domain}/api/campaigns/{campaign_id}/status", auth=auth, json={"status": "running"}
        )
        if send_res.status_code >= 400:
            raise SocialPostError(f"listmonk campaign send failed: {send_res.text}")
        return {"status": "posted", "postId": str(campaign_id), "releaseURL": f"{domain}/admin/campaigns/{campaign_id}"}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        domain = credentials["domain"]
        auth = (credentials["api_user"], credentials["api_key"])
        res = await request_with_retry("GET", f"{domain}/api/campaigns/{post_id}/stats", auth=auth)
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        stats = res.json().get("data", {})
        return {
            "impressions": stats.get("views", 0),
            "likes": 0,
            "reposts": 0,
            "comments": 0,
            "clicks": stats.get("clicks", 0),
        }
