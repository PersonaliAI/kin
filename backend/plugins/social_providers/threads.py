"""Threads (Meta) — its own OAuth app family, separate from the main Facebook
app used for Facebook/Instagram. Requires a Threads app at
https://developers.facebook.com/apps (add the "Threads API" product). Env:
THREADS_APP_ID, THREADS_APP_SECRET, THREADS_REDIRECT_URI.

Token flow is two-step (short-lived code exchange, then long-lived token
exchange) and posting is two-step (create a media container, then publish
it) — both per Meta's documented Threads API.
"""

from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://threads.net/oauth/authorize"
SHORT_TOKEN_URL = "https://graph.threads.net/oauth/access_token"
LONG_TOKEN_URL = "https://graph.threads.net/access_token"
API_BASE = "https://graph.threads.net/v1.0"
SCOPES = "threads_basic,threads_content_publish"


class ThreadsProvider(SocialProvider):
    identifier = "threads"
    name = "Threads"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("THREADS_APP_ID"),
            "redirect_uri": env_or_error("THREADS_REDIRECT_URI"),
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            short_res = await client.post(
                SHORT_TOKEN_URL,
                data={
                    "client_id": env_or_error("THREADS_APP_ID"),
                    "client_secret": env_or_error("THREADS_APP_SECRET"),
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri or env_or_error("THREADS_REDIRECT_URI"),
                    "code": code,
                },
            )
            if short_res.status_code >= 400:
                raise SocialPostError(f"threads token exchange failed: {short_res.text}")
            short = short_res.json()

            long_res = await client.get(
                LONG_TOKEN_URL,
                params={
                    "grant_type": "th_exchange_token",
                    "client_secret": env_or_error("THREADS_APP_SECRET"),
                    "access_token": short["access_token"],
                },
            )
            long_res.raise_for_status()
            long_data = long_res.json()

            me_res = await client.get(
                f"{API_BASE}/me", params={"fields": "id,username", "access_token": long_data["access_token"]}
            )
            me_res.raise_for_status()
            me = me_res.json()

        return {
            "access_token": long_data["access_token"],
            "expires_in": long_data.get("expires_in", 5184000),
            "threads_user_id": me.get("id"),
            "username": me.get("username"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                "https://graph.threads.net/refresh_access_token",
                params={"grant_type": "th_refresh_token", "access_token": credentials["access_token"]},
            )
        if res.status_code >= 400:
            raise NeedsReconnect("threads: token refresh failed, reconnect required")
        data = res.json()
        return {**credentials, "access_token": data["access_token"], "expires_in": data.get("expires_in", 5184000)}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        user_id = credentials["threads_user_id"]
        access_token = credentials["access_token"]
        params: dict[str, Any] = {"text": content, "access_token": access_token}
        params["media_type"] = "IMAGE" if media_urls else "TEXT"
        if media_urls:
            params["image_url"] = media_urls[0]
        reply_control = settings.get("reply_control")
        if reply_control in ("everyone", "accounts_you_follow", "mentioned_only"):
            params["reply_control"] = reply_control

        container_res = await request_with_retry(
            "POST", f"{API_BASE}/{user_id}/threads", params=params
        )
        if container_res.status_code >= 400:
            raise SocialPostError(f"threads container create failed: {container_res.text}")
        container_id = container_res.json().get("id")

        publish_res = await request_with_retry(
            "POST",
            f"{API_BASE}/{user_id}/threads_publish",
            params={"creation_id": container_id, "access_token": access_token},
        )
        if publish_res.status_code >= 400:
            raise SocialPostError(f"threads publish failed: {publish_res.text}")
        post_id = publish_res.json().get("id", "")
        return {"status": "posted", "postId": post_id, "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET",
            f"{API_BASE}/{post_id}/insights",
            params={
                "metric": "views,likes,replies,reposts,quotes",
                "access_token": credentials["access_token"],
            },
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        metrics = {m["name"]: m.get("values", [{}])[0].get("value", 0) for m in res.json().get("data", [])}
        return {
            "impressions": metrics.get("views", 0),
            "likes": metrics.get("likes", 0),
            "reposts": metrics.get("reposts", 0),
            "comments": metrics.get("replies", 0),
            "clicks": 0,
        }
