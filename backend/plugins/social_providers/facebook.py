"""Facebook Pages — OAuth2 via a Meta app (shared with instagram.py/gmb.py
per Postiz's .env.example convention: one FACEBOOK_APP_ID/SECRET drives all
three Meta-family surfaces). Requires an app at
https://developers.facebook.com/apps with the "Facebook Login" + Pages
permissions (pages_manage_posts, pages_read_engagement, pages_show_list)
approved. Env: FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_REDIRECT_URI.

Facebook posts always go to a Page (not the personal profile, which the
Graph API no longer allows posting to) — the first Page returned by
/me/accounts is used automatically.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

GRAPH_VERSION = "v21.0"
AUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
SCOPES = "pages_manage_posts,pages_read_engagement,pages_show_list,business_management"


class FacebookProvider(SocialProvider):
    identifier = "facebook"
    name = "Facebook"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("FACEBOOK_APP_ID"),
            "redirect_uri": env_or_error("FACEBOOK_REDIRECT_URI"),
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def _pages(self, user_access_token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={"access_token": user_access_token},
            )
        res.raise_for_status()
        return res.json().get("data", [])

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                TOKEN_URL,
                params={
                    "client_id": env_or_error("FACEBOOK_APP_ID"),
                    "client_secret": env_or_error("FACEBOOK_APP_SECRET"),
                    "redirect_uri": redirect_uri or env_or_error("FACEBOOK_REDIRECT_URI"),
                    "code": code,
                },
            )
        if res.status_code >= 400:
            raise SocialPostError(f"facebook token exchange failed: {res.text}")
        user_token = res.json()["access_token"]

        pages = await self._pages(user_token)
        if not pages:
            raise SocialPostError("facebook: no Pages found on this account — create/admin a Page first")
        page = pages[0]
        return {
            "user_access_token": user_token,
            "page_id": page["id"],
            "page_name": page.get("name"),
            "access_token": page["access_token"],  # page token; used for posting
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        # Page access tokens obtained this way don't expire unless the user
        # revokes access; nothing to actively refresh.
        return credentials

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        page_id = credentials["page_id"]
        access_token = credentials["access_token"]
        if media_urls:
            res = await request_with_retry(
                "POST",
                f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/photos",
                data={"url": media_urls[0], "caption": content, "access_token": access_token},
            )
        else:
            res = await request_with_retry(
                "POST",
                f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/feed",
                data={"message": content, "access_token": access_token},
            )
        if res.status_code >= 400:
            raise SocialPostError(f"facebook post failed ({res.status_code}): {res.text}")
        data = res.json()
        post_id = data.get("post_id") or data.get("id", "")
        return {"status": "posted", "postId": post_id, "releaseURL": f"https://www.facebook.com/{post_id}" if post_id else ""}

    async def comment(self, post_id: str, content: str, credentials: dict[str, Any]) -> dict[str, Any]:
        res = await request_with_retry(
            "POST",
            f"https://graph.facebook.com/{GRAPH_VERSION}/{post_id}/comments",
            data={"message": content, "access_token": credentials["access_token"]},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"facebook comment failed: {res.text}")
        return {"status": "posted", "postId": res.json().get("id", ""), "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET",
            f"https://graph.facebook.com/{GRAPH_VERSION}/{post_id}",
            params={
                "fields": "insights.metric(post_impressions,post_clicks),likes.summary(true),comments.summary(true),shares",
                "access_token": credentials["access_token"],
            },
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        data = res.json()
        insights = {
            v["name"]: v.get("values", [{}])[0].get("value", 0)
            for v in data.get("insights", {}).get("data", [])
        }
        return {
            "impressions": insights.get("post_impressions", 0),
            "likes": data.get("likes", {}).get("summary", {}).get("total_count", 0),
            "reposts": data.get("shares", {}).get("count", 0),
            "comments": data.get("comments", {}).get("summary", {}).get("total_count", 0),
            "clicks": insights.get("post_clicks", 0),
        }
