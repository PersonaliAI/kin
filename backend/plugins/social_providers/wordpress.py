"""WordPress (self-hosted) — Application Passwords (built into WP core
5.6+): user creates one at wp-admin > Users > Profile > Application
Passwords, pastes their WP username + the generated app password. Basic
Auth against the site's own REST API, no OAuth, no WordPress.com dependency.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class WordPressProvider(SocialProvider):
    identifier = "wordpress"
    name = "WordPress"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        site_url = (form.get("instance_url") or "").strip().rstrip("/")
        username = (form.get("username") or "").strip()
        app_password = (form.get("api_key") or "").strip()
        if not site_url or not username or not app_password:
            raise SocialPostError("Enter your WordPress site URL, username, and application password")
        if not site_url.startswith("http"):
            site_url = f"https://{site_url}"
        token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        res = await request_with_retry(
            "GET", f"{site_url}/wp-json/wp/v2/users/me", headers={"Authorization": f"Basic {token}"}
        )
        if res.status_code >= 400:
            raise SocialPostError("WordPress rejected that username/application password")
        return {"site_url": site_url, "basic_auth": token}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        site_url = credentials["site_url"]
        headers = {"Authorization": f"Basic {credentials['basic_auth']}"}
        title, _, body = content.partition("\n")
        html = (body or content).replace("\n", "<br>")
        media_id = None
        if media_urls:
            img = await request_with_retry("GET", media_urls[0])
            up = await request_with_retry(
                "POST", f"{site_url}/wp-json/wp/v2/media", headers={
                    **headers, "Content-Disposition": "attachment; filename=media.jpg",
                },
                content=img.content,
            )
            if up.status_code < 400:
                media_id = up.json().get("id")

        body_payload: dict[str, Any] = {
            "title": title[:200] or "New post",
            "content": html,
            "status": "publish",
        }
        if media_id:
            body_payload["featured_media"] = media_id
        res = await request_with_retry(
            "POST", f"{site_url}/wp-json/wp/v2/posts", headers=headers, json=body_payload
        )
        if res.status_code >= 400:
            raise SocialPostError(f"wordpress post failed ({res.status_code}): {res.text}")
        data = res.json()
        return {"status": "posted", "postId": str(data.get("id", "")), "releaseURL": data.get("link", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Core WP REST API has no built-in view/like counters (Jetpack Stats
        # would be needed, a separate plugin-specific API).
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
