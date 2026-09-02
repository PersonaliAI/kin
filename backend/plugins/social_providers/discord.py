"""Discord — connected via an Incoming Webhook URL (Server Settings >
Integrations > Webhooks in the target channel), not OAuth2. This is
deliberately simpler than Postiz's bot-install + guild/channel picker flow —
no Discord application needs to be registered, and it works immediately
without a bot being invited anywhere. Real Discord Bot OAuth (channel
picker) can replace this later if per-channel selection UI is built.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class DiscordProvider(SocialProvider):
    identifier = "discord"
    name = "Discord"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        webhook_url = (form.get("webhook_url") or "").strip()
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            raise SocialPostError("Paste a valid Discord channel webhook URL")
        res = await request_with_retry("GET", webhook_url)
        if res.status_code >= 400:
            raise SocialPostError("That Discord webhook URL doesn't work (check it hasn't been deleted)")
        info = res.json()
        return {
            "webhook_url": webhook_url,
            "channel_id": info.get("channel_id"),
            "guild_id": info.get("guild_id"),
            "name": info.get("name"),
        }

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        webhook_url = credentials["webhook_url"]
        body: dict[str, Any] = {"content": content[:2000]}
        if media_urls:
            body["embeds"] = [{"image": {"url": media_urls[0]}}]
        if settings.get("username"):
            body["username"] = settings["username"][:80]
        if settings.get("suppress_mentions"):
            body["allowed_mentions"] = {"parse": []}
        res = await request_with_retry("POST", f"{webhook_url}?wait=true", json=body)
        if res.status_code >= 400:
            raise SocialPostError(f"discord post failed ({res.status_code}): {res.text}")
        data = res.json()
        message_id = data.get("id", "")
        channel_id = credentials.get("channel_id", "")
        guild_id = credentials.get("guild_id", "")
        url = (
            f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            if guild_id and channel_id and message_id
            else ""
        )
        return {"status": "posted", "postId": message_id, "releaseURL": url}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Webhooks have no read access to reactions/views — Discord's bot API
        # would be needed for that, out of scope for the webhook-only connect.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
