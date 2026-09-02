"""Telegram — bot token (no OAuth). Defaults to Kin's own existing global
Telegram bot (TELEGRAM_BOT_TOKEN, already used for the Chatty webhook) so
the user only has to add that bot as admin of their channel and give us the
channel's @username or numeric chat id; they can alternatively supply their
own bot token if they'd rather not use Kin's shared bot.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class TelegramProvider(SocialProvider):
    identifier = "telegram"
    name = "Telegram"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        chat_id = (form.get("chat_id") or "").strip()
        bot_token = (form.get("api_key") or "").strip() or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not chat_id:
            raise SocialPostError("Enter the channel/chat id (or @username) to post to")
        if not bot_token:
            raise SocialPostError("No Telegram bot token configured")
        res = await request_with_retry(
            "GET", f"https://api.telegram.org/bot{bot_token}/getChat", params={"chat_id": chat_id}
        )
        if res.status_code >= 400 or not res.json().get("ok"):
            raise SocialPostError("Telegram couldn't find that chat — make sure the bot is an admin there")
        return {"bot_token": bot_token, "chat_id": chat_id}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        bot_token = credentials["bot_token"]
        chat_id = credentials["chat_id"]
        disable_notification = bool(settings.get("disable_notification", False))
        if media_urls:
            res = await request_with_retry(
                "POST", f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                json={
                    "chat_id": chat_id, "photo": media_urls[0], "caption": content[:1024],
                    "disable_notification": disable_notification,
                },
            )
        else:
            res = await request_with_retry(
                "POST", f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id, "text": content[:4096],
                    "disable_notification": disable_notification,
                    "disable_web_page_preview": bool(settings.get("disable_web_page_preview", False)),
                },
            )
        data = res.json()
        if res.status_code >= 400 or not data.get("ok"):
            raise SocialPostError(f"telegram post failed: {data}")
        message = data["result"]
        message_id = message.get("message_id", "")
        username = (message.get("chat") or {}).get("username")
        url = f"https://t.me/{username}/{message_id}" if username and message_id else ""
        return {"status": "posted", "postId": str(message_id), "releaseURL": url}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Bot API doesn't expose view counts for channel posts.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
