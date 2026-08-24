"""YouTube — its own Google OAuth connection (separate from the primary
Google Calendar/Gmail connection), scoped to youtube.upload. Reuses
GOOGLE_CLIENT_ID/SECRET; needs its own YOUTUBE_REDIRECT_URI registered as an
additional redirect URI on the same OAuth client.

`content` is used as "title\\ndescription" (first line = title, capped at
100 chars per YouTube's limit); media_urls[0] must be a video file URL.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


class YouTubeProvider(OAuth2Mixin, SocialProvider):
    identifier = "youtube"
    name = "YouTube"
    max_concurrent_jobs = 1
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
    CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
    REDIRECT_URI_ENV = "YOUTUBE_REDIRECT_URI"
    SCOPES = SCOPES
    EXTRA_AUTH_PARAMS = {"access_type": "offline", "prompt": "consent"}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not media_urls:
            raise SocialPostError("youtube: a video is required")
        title, _, description = content.partition("\n")
        title = (title or "New video")[:100]

        video_res = await request_with_retry("GET", media_urls[0])
        if video_res.status_code >= 400:
            raise SocialPostError("youtube: could not fetch video file for upload")

        settings = settings or {}
        metadata = {
            "snippet": {"title": title, "description": description or content},
            "status": {
                "privacyStatus": settings.get("privacy", "public"),
                "selfDeclaredMadeForKids": bool(settings.get("made_for_kids", False)),
            },
        }
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"part": "snippet,status", "uploadType": "multipart"},
                headers=headers,
                files={
                    "metadata": (None, json.dumps(metadata), "application/json"),
                    "video": ("video.mp4", video_res.content, "video/*"),
                },
            )
        if res.status_code >= 400:
            raise SocialPostError(f"youtube upload failed ({res.status_code}): {res.text}")
        data = res.json()
        video_id = data.get("id", "")
        return {
            "status": "posted",
            "postId": video_id,
            "releaseURL": f"https://youtube.com/watch?v={video_id}" if video_id else "",
        }

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET",
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": post_id},
            headers={"Authorization": f"Bearer {credentials['access_token']}"},
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        items = res.json().get("items", [])
        if not items:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        stats = items[0].get("statistics", {})
        return {
            "impressions": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "reposts": 0,
            "comments": int(stats.get("commentCount", 0)),
            "clicks": 0,
        }
