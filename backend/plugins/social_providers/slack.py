"""Slack — connected via an Incoming Webhook URL (create one at
https://api.slack.com/apps -> "Incoming Webhooks" -> "Add New Webhook to
Workspace", or via a workspace admin's Slack App Directory), not OAuth2. No
Kin-registered Slack app needed — the user brings their own webhook URL, the
same BYOK pattern used for Discord.

Previously this went through a custom "Add to Slack" OAuth2 app (requiring
SLACK_CLIENT_ID/SECRET registered by Kin) purely to get the user to a channel
picker; the thing actually stored and posted with was always just the
resulting webhook_url. Cutting the OAuth app out entirely removes that
central dependency with no loss of functionality.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class SlackProvider(SocialProvider):
    identifier = "slack"
    name = "Slack"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        webhook_url = (form.get("webhook_url") or "").strip()
        if not webhook_url.startswith("https://hooks.slack.com/services/"):
            raise SocialPostError("Paste a valid Slack Incoming Webhook URL")
        # Slack webhooks are POST-only — there's no GET-based info endpoint
        # like Discord's to validate non-destructively, so validation doubles
        # as a visible confirmation message in the target channel.
        res = await request_with_retry(
            "POST", webhook_url, json={"text": "✅ Kin is now connected to this channel."}
        )
        if res.status_code >= 400 or res.text.strip() != "ok":
            raise SocialPostError("That Slack webhook URL doesn't work (check it hasn't been revoked)")
        return {"webhook_url": webhook_url, "team": (form.get("team") or "").strip() or None}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            raise SocialPostError("slack: no webhook on file, reconnect required")
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
        # Incoming webhooks have no read access to reactions/views.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
