"""Tumblr — OAuth2 (Tumblr added OAuth2 support to API v2 in 2021; NPF post
format). Requires an app at https://www.tumblr.com/oauth/apps. Env:
TUMBLR_CLIENT_ID, TUMBLR_CLIENT_SECRET, TUMBLR_REDIRECT_URI.

Posts go to a specific blog under the account; defaults to the user's
primary blog captured at connect time.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://www.tumblr.com/oauth2/authorize"
TOKEN_URL = "https://api.tumblr.com/v2/oauth2/token"


class TumblrProvider(OAuth2Mixin, SocialProvider):
    identifier = "tumblr"
    name = "Tumblr"
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "TUMBLR_CLIENT_ID"
    CLIENT_SECRET_ENV = "TUMBLR_CLIENT_SECRET"
    REDIRECT_URI_ENV = "TUMBLR_REDIRECT_URI"
    SCOPES = "write offline_access"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        creds = await super().exchange_code(code, redirect_uri)
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                "https://api.tumblr.com/v2/user/info",
                headers={"Authorization": f"Bearer {creds['access_token']}"},
            )
        if res.status_code < 400:
            blogs = res.json().get("response", {}).get("user", {}).get("blogs", [])
            if blogs:
                creds["blog_name"] = blogs[0]["name"]
        return creds

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        blog = credentials.get("blog_name")
        if not blog:
            raise SocialPostError("tumblr: no blog configured for this account")
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }
        blocks: list[dict[str, Any]] = [{"type": "text", "text": content}]
        if media_urls:
            blocks.append({"type": "image", "media": [{"url": media_urls[0]}]})
        body = {"content": blocks, "state": "published"}
        res = await request_with_retry(
            "POST", f"https://api.tumblr.com/v2/blog/{blog}/posts", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise SocialPostError(f"tumblr post failed ({res.status_code}): {res.text}")
        data = res.json().get("response", {})
        post_id = str(data.get("id", ""))
        return {"status": "posted", "postId": post_id, "releaseURL": data.get("post_url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        blog = credentials.get("blog_name")
        if not post_id or not blog:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        res = await request_with_retry(
            "GET", f"https://api.tumblr.com/v2/blog/{blog}/posts?id={post_id}&notes_info=true", headers=headers
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        posts = res.json().get("response", {}).get("posts", [])
        if not posts:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        p = posts[0]
        return {
            "impressions": 0,
            "likes": p.get("note_count", 0),
            "reposts": 0,
            "comments": 0,
            "clicks": 0,
        }
