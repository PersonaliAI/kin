"""Farcaster — posted via Neynar (https://neynar.com), the standard managed
API for Farcaster (posting directly against a Farcaster hub requires running
hub infrastructure and ed25519-signing your own registered signer, which
Neynar abstracts away). Requires a Neynar API key (env NEYNAR_API_KEY, one
key shared across all Kin users, like the Telegram bot) plus a per-user
"signer" that the user approves once in Warpcast via Neynar's managed-signer
flow (https://docs.neynar.com/docs/create-a-signer) — connect_manual just
stores the resulting signer_uuid.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry

API_BASE = "https://api.neynar.com/v2/farcaster"


def _api_key() -> str:
    v = os.environ.get("NEYNAR_API_KEY")
    if not v:
        raise SocialPostError("NEYNAR_API_KEY not configured")
    return v


class FarcasterProvider(SocialProvider):
    identifier = "farcaster"
    name = "Farcaster"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        signer_uuid = (form.get("api_key") or "").strip()
        if not signer_uuid:
            raise SocialPostError(
                "Enter your Neynar signer_uuid (create one at neynar.com and approve it in Warpcast)"
            )
        res = await request_with_retry(
            "GET", f"{API_BASE}/signer", params={"signer_uuid": signer_uuid},
            headers={"api_key": _api_key()},
        )
        if res.status_code >= 400 or res.json().get("status") != "approved":
            raise SocialPostError("That signer isn't approved yet — approve it in Warpcast first")
        return {"signer_uuid": signer_uuid, "fid": res.json().get("fid")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        body: dict[str, Any] = {"signer_uuid": credentials["signer_uuid"], "text": content[:320]}
        if media_urls:
            body["embeds"] = [{"url": media_urls[0]}]
        if settings.get("channel_id"):
            body["channel_id"] = settings["channel_id"]
        res = await request_with_retry(
            "POST", f"{API_BASE}/cast", headers={"api_key": _api_key(), "Content-Type": "application/json"}, json=body
        )
        if res.status_code >= 400:
            raise SocialPostError(f"farcaster cast failed ({res.status_code}): {res.text}")
        cast = res.json().get("cast", {})
        cast_hash = cast.get("hash", "")
        return {"status": "posted", "postId": cast_hash, "releaseURL": f"https://warpcast.com/~/conversations/{cast_hash}" if cast_hash else ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET", f"{API_BASE}/cast", params={"identifier": post_id, "type": "hash"},
            headers={"api_key": _api_key()},
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        reactions = res.json().get("cast", {}).get("reactions", {})
        return {
            "impressions": 0,
            "likes": reactions.get("likes_count", 0),
            "reposts": reactions.get("recasts_count", 0),
            "comments": res.json().get("cast", {}).get("replies", {}).get("count", 0),
            "clicks": 0,
        }
