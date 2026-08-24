"""Instagram (Business/Creator, via Instagram Graph API) — same Meta app as
facebook.py; requires the connected account be an Instagram Business or
Creator account linked to a Facebook Page. Env: reuses FACEBOOK_APP_ID,
FACEBOOK_APP_SECRET; INSTAGRAM_REDIRECT_URI for the callback route.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import SocialPostError, SocialProvider, env_or_error, request_with_retry
from .facebook import GRAPH_VERSION, SCOPES as FB_SCOPES, TOKEN_URL

AUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
SCOPES = FB_SCOPES + ",instagram_basic,instagram_content_publish"


class InstagramProvider(SocialProvider):
    identifier = "instagram"
    name = "Instagram"
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "client_id": env_or_error("FACEBOOK_APP_ID"),
            "redirect_uri": env_or_error("INSTAGRAM_REDIRECT_URI"),
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_res = await client.get(
                TOKEN_URL,
                params={
                    "client_id": env_or_error("FACEBOOK_APP_ID"),
                    "client_secret": env_or_error("FACEBOOK_APP_SECRET"),
                    "redirect_uri": redirect_uri or env_or_error("INSTAGRAM_REDIRECT_URI"),
                    "code": code,
                },
            )
            if token_res.status_code >= 400:
                raise SocialPostError(f"instagram token exchange failed: {token_res.text}")
            user_token = token_res.json()["access_token"]

            pages_res = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={"access_token": user_token},
            )
            pages_res.raise_for_status()
            pages = pages_res.json().get("data", [])
            if not pages:
                raise SocialPostError("instagram: no linked Facebook Page found")

            ig_user_id = None
            page_access_token = None
            for page in pages:
                info_res = await client.get(
                    f"https://graph.facebook.com/{GRAPH_VERSION}/{page['id']}",
                    params={"fields": "instagram_business_account", "access_token": page["access_token"]},
                )
                ig = info_res.json().get("instagram_business_account")
                if ig:
                    ig_user_id = ig["id"]
                    page_access_token = page["access_token"]
                    break

        if not ig_user_id:
            raise SocialPostError(
                "instagram: no Instagram Business/Creator account linked to any of your Facebook Pages"
            )
        return {"access_token": page_access_token, "ig_user_id": ig_user_id}

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        return credentials

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not media_urls:
            raise SocialPostError("instagram: posts require an image or video")
        ig_user_id = credentials["ig_user_id"]
        access_token = credentials["access_token"]

        container_res = await request_with_retry(
            "POST",
            f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media",
            data={"image_url": media_urls[0], "caption": content, "access_token": access_token},
        )
        if container_res.status_code >= 400:
            raise SocialPostError(f"instagram media container failed: {container_res.text}")
        creation_id = container_res.json().get("id")

        publish_res = await request_with_retry(
            "POST",
            f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token},
        )
        if publish_res.status_code >= 400:
            raise SocialPostError(f"instagram publish failed: {publish_res.text}")
        media_id = publish_res.json().get("id", "")
        return {"status": "posted", "postId": media_id, "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        res = await request_with_retry(
            "GET",
            f"https://graph.facebook.com/{GRAPH_VERSION}/{post_id}/insights",
            params={"metric": "impressions,reach,likes,comments,saved", "access_token": credentials["access_token"]},
        )
        if res.status_code >= 400:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        metrics = {v["name"]: v.get("values", [{}])[0].get("value", 0) for v in res.json().get("data", [])}
        return {
            "impressions": metrics.get("impressions", 0),
            "likes": metrics.get("likes", 0),
            "reposts": 0,
            "comments": metrics.get("comments", 0),
            "clicks": 0,
        }
