"""Lemmy — self-hosted, instance-per-user. Logs in with username/password
against the chosen instance's API (POST /api/v3/user/login) to obtain a JWT,
rather than OAuth (Lemmy has no OAuth2 provider support). Posting requires a
target community id, captured by name at connect time.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry


class LemmyProvider(SocialProvider):
    identifier = "lemmy"
    name = "Lemmy"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        instance = (form.get("instance_url") or "").strip().rstrip("/")
        username = (form.get("username") or "").strip()
        password = (form.get("api_key") or "").strip()
        community = (form.get("community") or "").strip()
        if not instance or not username or not password or not community:
            raise SocialPostError("Enter your Lemmy instance URL, username, password, and target community")
        if not instance.startswith("http"):
            instance = f"https://{instance}"

        login_res = await request_with_retry(
            "POST", f"{instance}/api/v3/user/login",
            json={"username_or_email": username, "password": password},
        )
        if login_res.status_code >= 400:
            raise SocialPostError("Lemmy rejected that username/password")
        jwt = login_res.json().get("jwt")
        if not jwt:
            raise SocialPostError("Lemmy login did not return a token (2FA accounts aren't supported here)")

        community_res = await request_with_retry(
            "GET", f"{instance}/api/v3/community", params={"name": community}
        )
        if community_res.status_code >= 400:
            raise SocialPostError(f"Could not find community '{community}' on {instance}")
        community_id = community_res.json().get("community_view", {}).get("community", {}).get("id")

        return {"instance_url": instance, "jwt": jwt, "community_id": community_id}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        instance = credentials["instance_url"]
        title, _, body = content.partition("\n")
        body_payload: dict[str, Any] = {
            "name": title[:200] or "New post",
            "community_id": credentials["community_id"],
            "body": body or content,
            "auth": credentials["jwt"],
        }
        if media_urls:
            body_payload["url"] = media_urls[0]
        res = await request_with_retry("POST", f"{instance}/api/v3/post", json=body_payload)
        if res.status_code >= 400:
            raise SocialPostError(f"lemmy post failed ({res.status_code}): {res.text}")
        post = res.json().get("post_view", {}).get("post", {})
        post_id = str(post.get("id", ""))
        return {"status": "posted", "postId": post_id, "releaseURL": f"{instance}/post/{post_id}" if post_id else ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        instance = credentials["instance_url"]
        res = await request_with_retry("GET", f"{instance}/api/v3/post", params={"id": post_id})
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        counts = res.json().get("post_view", {}).get("counts", {})
        return {
            "impressions": 0,
            "likes": counts.get("score", 0),
            "reposts": 0,
            "comments": counts.get("comments", 0),
            "clicks": 0,
        }
