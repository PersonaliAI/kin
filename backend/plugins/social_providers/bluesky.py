"""Bluesky — AT Protocol app password (no OAuth2; Bluesky's OAuth is still
maturing and most third-party tools use app passwords). User generates one
at Settings > App Passwords > Add App Password.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .base import NeedsReconnect, SocialPostError, SocialProvider, request_with_retry


class BlueskyProvider(SocialProvider):
    identifier = "bluesky"
    name = "Bluesky"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        identifier = (form.get("username") or "").strip()
        app_password = (form.get("api_key") or "").strip()
        pds_url = (form.get("instance_url") or "https://bsky.social").strip().rstrip("/")
        if not identifier or not app_password:
            raise SocialPostError("Enter your Bluesky handle and app password")
        res = await request_with_retry(
            "POST", f"{pds_url}/xrpc/com.atproto.server.createSession",
            json={"identifier": identifier, "password": app_password},
        )
        if res.status_code >= 400:
            raise SocialPostError("Bluesky rejected that handle/app password")
        data = res.json()
        return {
            "pds_url": pds_url,
            "identifier": identifier,
            "app_password": app_password,
            "access_jwt": data["accessJwt"],
            "refresh_jwt": data["refreshJwt"],
            "did": data["did"],
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        pds_url = credentials["pds_url"]
        res = await request_with_retry(
            "POST", f"{pds_url}/xrpc/com.atproto.server.refreshSession",
            headers={"Authorization": f"Bearer {credentials['refresh_jwt']}"},
        )
        if res.status_code >= 400:
            raise NeedsReconnect("bluesky: session refresh failed, reconnect required")
        data = res.json()
        return {**credentials, "access_jwt": data["accessJwt"], "refresh_jwt": data["refreshJwt"]}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        pds_url = credentials["pds_url"]
        headers = {"Authorization": f"Bearer {credentials['access_jwt']}"}
        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": content[:300],
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if media_urls:
            img_res = await request_with_retry("GET", media_urls[0])
            upload_res = await request_with_retry(
                "POST", f"{pds_url}/xrpc/com.atproto.repo.uploadBlob",
                headers={**headers, "Content-Type": img_res.headers.get("content-type", "image/jpeg")},
                content=img_res.content,
            )
            if upload_res.status_code < 400:
                blob = upload_res.json().get("blob")
                record["embed"] = {"$type": "app.bsky.embed.images", "images": [{"image": blob, "alt": ""}]}

        res = await request_with_retry(
            "POST", f"{pds_url}/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json={"repo": credentials["did"], "collection": "app.bsky.feed.post", "record": record},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"bluesky post failed ({res.status_code}): {res.text}")
        data = res.json()
        uri = data.get("uri", "")
        rkey = uri.split("/")[-1] if uri else ""
        handle = credentials.get("identifier", "")
        url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
        return {"status": "posted", "postId": uri, "releaseURL": url}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        pds_url = credentials["pds_url"]
        res = await request_with_retry(
            "GET", f"{pds_url}/xrpc/app.bsky.feed.getPostThread",
            headers={"Authorization": f"Bearer {credentials['access_jwt']}"},
            params={"uri": post_id},
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        post = res.json().get("thread", {}).get("post", {})
        return {
            "impressions": 0,
            "likes": post.get("likeCount", 0),
            "reposts": post.get("repostCount", 0),
            "comments": post.get("replyCount", 0),
            "clicks": 0,
        }
