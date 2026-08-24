"""Nostr — connected with a raw private key (hex, not bech32 nsec — convert
with any Nostr client's "export as hex" option first), since Nostr has no
OAuth concept at all: identity *is* a keypair. Events are BIP340-Schnorr
signed (via `coincurve`) and published by opening a short-lived WebSocket to
each configured relay and sending ["EVENT", event] — Nostr's publish path is
WebSocket-only, there is no HTTP alternative in the protocol.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import websockets
from coincurve import PrivateKey

from .base import SocialPostError, SocialProvider

DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]


def _event_id(pubkey_hex: str, created_at: int, kind: int, tags: list, content: str) -> bytes:
    serialized = json.dumps(
        [0, pubkey_hex, created_at, kind, tags, content], separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).digest()


async def _publish_to_relay(relay_url: str, event: dict[str, Any]) -> bool:
    try:
        async with websockets.connect(relay_url, open_timeout=10) as ws:
            await ws.send(json.dumps(["EVENT", event]))
            for _ in range(3):
                reply = json.loads(await ws.recv())
                if reply[0] == "OK":
                    return bool(reply[2])
    except Exception:
        return False
    return False


class NostrProvider(SocialProvider):
    identifier = "nostr"
    name = "Nostr"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        privkey_hex = (form.get("api_key") or "").strip().lower()
        if len(privkey_hex) != 64:
            raise SocialPostError("Enter your Nostr private key as 64 hex characters (not nsec1...)")
        try:
            pk = PrivateKey(bytes.fromhex(privkey_hex))
        except (ValueError, Exception):
            raise SocialPostError("That doesn't look like a valid Nostr private key")
        pubkey_hex = pk.public_key.format(compressed=True)[1:].hex()
        relays = [r.strip() for r in (form.get("relays") or "").split(",") if r.strip()] or DEFAULT_RELAYS
        return {"private_key": privkey_hex, "public_key": pubkey_hex, "relays": relays}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        pk = PrivateKey(bytes.fromhex(credentials["private_key"]))
        pubkey_hex = credentials["public_key"]
        created_at = int(time.time())
        text = f"{content}\n{media_urls[0]}" if media_urls else content

        event_id = _event_id(pubkey_hex, created_at, 1, [], text)
        signature = pk.sign_schnorr(event_id).hex()
        event = {
            "id": event_id.hex(),
            "pubkey": pubkey_hex,
            "created_at": created_at,
            "kind": 1,
            "tags": [],
            "content": text,
            "sig": signature,
        }

        relays = credentials.get("relays") or DEFAULT_RELAYS
        accepted = False
        for relay in relays:
            if await _publish_to_relay(relay, event):
                accepted = True
        if not accepted:
            raise SocialPostError("nostr: no relay accepted the event")

        return {"status": "posted", "postId": event["id"], "releaseURL": f"https://njump.me/{event['id']}"}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # Reaction/repost counts require querying relays for kind:7/kind:6
        # events referencing this id — a much bigger subscribe-and-collect
        # operation than fits the simple publish-only flow above.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
