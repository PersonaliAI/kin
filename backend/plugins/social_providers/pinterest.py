"""Pinterest — OAuth2, ported from postiz-app's pinterest.provider.ts.
Requires an app at https://developers.pinterest.com/apps with the
"Standard API" trial access approved for pins:write. Env:
PINTEREST_CLIENT_ID, PINTEREST_CLIENT_SECRET, PINTEREST_REDIRECT_URI.

Pins always belong to a board; media is required (Pinterest doesn't support
text-only pins). Uses the account's first board unless
credentials["board_id"] was set explicitly.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"


class PinterestProvider(OAuth2Mixin, SocialProvider):
    identifier = "pinterest"
    name = "Pinterest"
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "PINTEREST_CLIENT_ID"
    CLIENT_SECRET_ENV = "PINTEREST_CLIENT_SECRET"
    REDIRECT_URI_ENV = "PINTEREST_REDIRECT_URI"
    SCOPES = "boards:read,pins:read,pins:write"
    BASIC_AUTH_TOKEN = True

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        creds = await super().exchange_code(code, redirect_uri)
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                "https://api.pinterest.com/v5/boards",
                headers={"Authorization": f"Bearer {creds['access_token']}"},
            )
        if res.status_code < 400:
            boards = res.json().get("items", [])
            if boards:
                creds["board_id"] = boards[0]["id"]
                creds["board_name"] = boards[0].get("name")
        return creds

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not media_urls:
            raise SocialPostError("pinterest: pins require an image")
        board_id = credentials.get("board_id")
        if not board_id:
            raise SocialPostError("pinterest: no board configured for this account")
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }
        body = {
            "board_id": board_id,
            "media_source": {"source_type": "image_url", "url": media_urls[0]},
            "description": content[:800],
        }
        res = await request_with_retry("POST", "https://api.pinterest.com/v5/pins", headers=headers, json=body)
        if res.status_code >= 400:
            raise SocialPostError(f"pinterest post failed ({res.status_code}): {res.text}")
        data = res.json()
        pin_id = data.get("id", "")
        return {"status": "posted", "postId": pin_id, "releaseURL": f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        res = await request_with_retry(
            "GET",
            f"https://api.pinterest.com/v5/pins/{post_id}/analytics?metric_types=IMPRESSION,PIN_CLICK,SAVE",
            headers=headers,
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        data = res.json().get("all", {}).get("lifetime_metrics", {})
        return {
            "impressions": data.get("IMPRESSION", 0),
            "likes": data.get("SAVE", 0),
            "reposts": 0,
            "comments": 0,
            "clicks": data.get("PIN_CLICK", 0),
        }
