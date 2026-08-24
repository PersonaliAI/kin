"""X (Twitter) — OAuth 2.0 Authorization Code flow with PKCE. Modern,
recommended path per X's current docs (over the OAuth 1.0a 3-legged flow
this used to use): supports refresh tokens, and doesn't need hand-rolled
HMAC-SHA1 request signing. Requires an app at
https://developer.x.com/en/portal with OAuth 2.0 enabled ("Web App,
Automated App or Bot" / confidential client). Env: X_CLIENT_ID,
X_CLIENT_SECRET, X_REDIRECT_URI.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
TWEETS_URL = "https://api.x.com/2/tweets"
SCOPES = "tweet.read tweet.write users.read offline.access"


class XProvider(SocialProvider):
    identifier = "x"
    name = "X (Twitter)"
    max_concurrent_jobs = 1
    oauth2 = True
    uses_pkce = True

    def generate_auth_url(self, state: str, pkce_challenge: Optional[str] = None) -> str:
        params = {
            "response_type": "code",
            "client_id": env_or_error("X_CLIENT_ID"),
            "redirect_uri": env_or_error("X_REDIRECT_URI"),
            "scope": SCOPES,
            "state": state,
            "code_challenge": pkce_challenge or "",
            "code_challenge_method": "S256",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, pkce_verifier: Optional[str] = None
    ) -> dict[str, Any]:
        auth = (env_or_error("X_CLIENT_ID"), env_or_error("X_CLIENT_SECRET"))
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri or env_or_error("X_REDIRECT_URI"),
                    "code_verifier": pkce_verifier or "",
                },
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if res.status_code >= 400:
                raise SocialPostError(f"x token exchange failed ({res.status_code}): {res.text}")
            tokens = res.json()

            me_res = await client.get(
                "https://api.x.com/2/users/me",
                params={"user.fields": "profile_image_url"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            me_data = me_res.json().get("data", {}) if me_res.status_code < 400 else {}
            username = me_data.get("username")
            # X returns a low-res "_normal" thumbnail by default; swap for
            # the full-size version, same trick every X client uses.
            avatar_url = (me_data.get("profile_image_url") or "").replace("_normal", "_400x400") or None

        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "avatar_url": avatar_url,
            "username": username,
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect("x: no refresh_token on file (offline.access scope missing?)")
        auth = (env_or_error("X_CLIENT_ID"), env_or_error("X_CLIENT_SECRET"))
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh},
                auth=auth,
            )
        if res.status_code >= 400:
            raise NeedsReconnect("x: refresh failed, reconnect required")
        tokens = res.json()
        return {
            **credentials,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh),
            "expires_in": tokens.get("expires_in"),
        }

    async def _upload_media(self, image_url: str, credentials: dict[str, Any]) -> Optional[str]:
        """X's v2 media endpoint accepts OAuth2 user-context Bearer tokens
        (unlike the legacy v1.1 upload.twitter.com endpoint, which is
        OAuth1.0a-only) — simple (non-chunked) upload, fine for images."""
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_res = await client.get(image_url)
            if img_res.status_code >= 400:
                return None
            up_res = await client.post(
                "https://api.x.com/2/media/upload",
                headers=headers,
                files={"media": ("media", img_res.content, img_res.headers.get("content-type", "image/jpeg"))},
                data={"media_category": "tweet_image"},
            )
        if up_res.status_code >= 400:
            logger_text = up_res.text
            raise SocialPostError(f"x: media upload failed: {logger_text}")
        return str(up_res.json().get("data", {}).get("id") or up_res.json().get("media_id_string"))

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        max_len = 25000 if settings.get("premium_format") else 280
        # Reject rather than silently truncate — cutting content off mid-word
        # (or mid-hashtag/URL) and posting it anyway is worse than failing
        # loudly with a clear reason, same as the missing-media checks below.
        if len(content) > max_len:
            raise SocialPostError(
                f"x: content is {len(content)} characters, over the {max_len}-character limit "
                f"({'enable premium_format for up to 25000' if max_len == 280 else 'even with premium_format'})"
            )
        body: dict[str, Any] = {"text": content}
        reply_settings = {"followed": "following", "mentioned": "mentionedUsers"}.get(settings.get("reply_privacy", ""))
        if reply_settings:
            body["reply_settings"] = reply_settings
        if media_urls:
            media_id = await self._upload_media(media_urls[0], credentials)
            if media_id:
                body["media"] = {"media_ids": [media_id]}

        headers = {"Authorization": f"Bearer {credentials['access_token']}", "Content-Type": "application/json"}
        res = await request_with_retry("POST", TWEETS_URL, headers=headers, json=body)
        if res.status_code >= 400:
            raise SocialPostError(f"x post failed ({res.status_code}): {res.text}")
        tweet_id = res.json().get("data", {}).get("id", "")
        username = credentials.get("username", "")
        url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id else ""
        return {"status": "posted", "postId": tweet_id, "releaseURL": url}

    async def comment(self, post_id: str, content: str, credentials: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {credentials['access_token']}", "Content-Type": "application/json"}
        body = {"text": content[:280], "reply": {"in_reply_to_tweet_id": post_id}}
        res = await request_with_retry("POST", TWEETS_URL, headers=headers, json=body)
        if res.status_code >= 400:
            raise SocialPostError(f"x reply failed ({res.status_code}): {res.text}")
        return {"status": "posted", "postId": res.json().get("data", {}).get("id", ""), "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        res = await request_with_retry(
            "GET", f"{TWEETS_URL}/{post_id}", headers=headers, params={"tweet.fields": "public_metrics"}
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        metrics = res.json().get("data", {}).get("public_metrics", {})
        return {
            "impressions": metrics.get("impression_count", 0),
            "likes": metrics.get("like_count", 0),
            "reposts": metrics.get("retweet_count", 0),
            "comments": metrics.get("reply_count", 0),
            "clicks": 0,
        }
