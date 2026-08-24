"""Slack — OAuth2 "Add to Slack" flow requesting the incoming-webhook scope,
so the user picks the target channel during the Slack consent screen itself
(no separate channel-picker UI needed on Kin's side). Requires a Slack app at
https://api.slack.com/apps with redirect URL + the `incoming-webhook` and
`chat:write` scopes. Env: SLACK_CLIENT_ID, SLACK_CLIENT_SECRET,
SLACK_REDIRECT_URI.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, env_or_error, request_with_retry

AUTH_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SCOPES = "incoming-webhook,chat:write"


class SlackProvider(SocialProvider):
    identifier = "slack"
    name = "Slack"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("SLACK_CLIENT_ID"),
            "redirect_uri": env_or_error("SLACK_REDIRECT_URI"),
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": env_or_error("SLACK_CLIENT_ID"),
                    "client_secret": env_or_error("SLACK_CLIENT_SECRET"),
                    "redirect_uri": redirect_uri or env_or_error("SLACK_REDIRECT_URI"),
                },
            )
        data = res.json()
        if not data.get("ok"):
            raise SocialPostError(f"slack oauth failed: {data.get('error')}")
        webhook = data.get("incoming_webhook") or {}
        return {
            "access_token": data.get("access_token"),
            "webhook_url": webhook.get("url"),
            "channel": webhook.get("channel"),
            "channel_id": webhook.get("channel_id"),
            "team": (data.get("team") or {}).get("name"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        # Slack bot tokens don't expire under the classic OAuth v2 flow used
        # here (no token rotation enabled) — nothing to refresh.
        return credentials

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            raise NeedsReconnect("slack: no webhook on file, reconnect required")
        body: dict[str, Any] = {"text": content}
        if media_urls:
            body["blocks"] = [
                {"type": "section", "text": {"type": "mrkdwn", "text": content}},
                {"type": "image", "image_url": media_urls[0], "alt_text": "attachment"},
            ]
        res = await request_with_retry("POST", webhook_url, json=body)
        if res.status_code >= 400 or res.text.strip() != "ok":
            raise SocialPostError(f"slack post failed ({res.status_code}): {res.text}")
        return {"status": "posted", "postId": "", "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Incoming webhooks don't return a message timestamp/channel needed
        # to look up reactions via chat:write scope alone.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
