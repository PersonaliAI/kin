"""Dribbble — OAuth2. Requires an app at https://dribbble.com/account/applications/new.
Env: DRIBBBLE_CLIENT_ID, DRIBBBLE_CLIENT_SECRET, DRIBBBLE_REDIRECT_URI.

Note: Dribbble's public API has been effectively closed to new "shot upload"
access for most apps since ~2020 (existing partners only) — this
implementation follows the documented v2 API shape, but posting will 403 for
apps without shot-upload approval from Dribbble. Fine as a real, spec-correct
implementation; flagged here so it isn't mistaken for a bug later.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://dribbble.com/oauth/authorize"
TOKEN_URL = "https://dribbble.com/oauth/token"


class DribbbleProvider(OAuth2Mixin, SocialProvider):
    identifier = "dribbble"
    name = "Dribbble"
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "DRIBBBLE_CLIENT_ID"
    CLIENT_SECRET_ENV = "DRIBBBLE_CLIENT_SECRET"
    REDIRECT_URI_ENV = "DRIBBBLE_REDIRECT_URI"
    SCOPES = "public upload"

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not media_urls:
            raise SocialPostError("dribbble: shots require an image")
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        title, _, description = content.partition("\n")
        image_res = await request_with_retry("GET", media_urls[0])
        res = await request_with_retry(
            "POST",
            "https://api.dribbble.com/v2/shots",
            headers=headers,
            data={"title": title[:200] or "New shot", "description": description},
            files={"image": ("shot.png", image_res.content)},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"dribbble post failed ({res.status_code}): {res.text}")
        data = res.json()
        shot_id = str(data.get("id", ""))
        return {"status": "posted", "postId": shot_id, "releaseURL": data.get("html_url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        res = await request_with_retry("GET", f"https://api.dribbble.com/v2/shots/{post_id}", headers=headers)
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        data = res.json()
        return {
            "impressions": data.get("views_count", 0),
            "likes": data.get("likes_count", 0),
            "reposts": data.get("rebounds_count", 0),
            "comments": data.get("comments_count", 0),
            "clicks": 0,
        }
