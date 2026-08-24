"""Reddit — OAuth2 (script-type "web app" flow), ported from postiz-app's
reddit.provider.ts. Requires an app at https://www.reddit.com/prefs/apps
(type "web app"). Env: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
REDDIT_REDIRECT_URI.

Reddit posts always go to a specific subreddit — since Kin's composer has no
per-post "target subreddit" field yet, this reads credentials["subreddit"]
(set once at connect time via connect_manual-style follow-up, or defaults to
crossposting to the user's own profile via "u_<username>").
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://www.reddit.com/api/v1/authorize"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
USER_AGENT = "web:kin-social-scheduler:v1.0 (by /u/kin-app)"


class RedditProvider(OAuth2Mixin, SocialProvider):
    identifier = "reddit"
    name = "Reddit"
    max_concurrent_jobs = 1
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "REDDIT_CLIENT_ID"
    CLIENT_SECRET_ENV = "REDDIT_CLIENT_SECRET"
    REDIRECT_URI_ENV = "REDDIT_REDIRECT_URI"
    SCOPES = "identity submit read"
    EXTRA_AUTH_PARAMS = {"duration": "permanent"}
    BASIC_AUTH_TOKEN = True

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        creds = await super().exchange_code(code, redirect_uri)
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                "https://oauth.reddit.com/api/v1/me",
                headers={"Authorization": f"Bearer {creds['access_token']}", "User-Agent": USER_AGENT},
            )
        if res.status_code < 400:
            username = res.json().get("name")
            creds["username"] = username
            creds["subreddit"] = f"u_{username}" if username else None
        return creds

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        subreddit = credentials.get("subreddit")
        if not subreddit:
            raise SocialPostError("reddit: no target subreddit configured for this account")
        title, _, body = content.partition("\n")
        title = title[:300] or "New post"
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "User-Agent": USER_AGENT,
        }
        data = {
            "sr": subreddit,
            "title": title,
            "api_type": "json",
        }
        if media_urls:
            data["kind"] = "image"
            data["url"] = media_urls[0]
        else:
            data["kind"] = "self"
            data["text"] = body or title

        res = await request_with_retry(
            "POST", "https://oauth.reddit.com/api/submit", headers=headers, data=data
        )
        if res.status_code >= 400:
            raise SocialPostError(f"reddit post failed ({res.status_code}): {res.text}")
        payload = res.json()
        errors = payload.get("json", {}).get("errors") or []
        if errors:
            raise SocialPostError(f"reddit post rejected: {errors}")
        post_data = payload.get("json", {}).get("data", {})
        name = post_data.get("name", "")
        return {"status": "posted", "postId": name, "releaseURL": post_data.get("url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "User-Agent": USER_AGENT,
        }
        res = await request_with_retry(
            "GET", f"https://oauth.reddit.com/api/info?id={post_id}", headers=headers
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        children = res.json().get("data", {}).get("children", [])
        if not children:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        d = children[0]["data"]
        return {
            "impressions": 0,
            "likes": d.get("score", 0),
            "reposts": 0,
            "comments": d.get("num_comments", 0),
            "clicks": 0,
        }
