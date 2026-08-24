"""LinkedIn provider — first real (non-stub) social provider, ported from
postiz-app's libraries/nestjs-libraries/src/integrations/social/linkedin.provider.ts,
trimmed to personal-profile posting (no company pages / carousel PDF yet —
those can be added in a follow-up batch).

Requires a LinkedIn app (https://www.linkedin.com/developers/apps) with the
"Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn" products
added. Env vars: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .base import NeedsReconnect, SocialPostError, SocialProvider, request_with_retry

logger = logging.getLogger("kin.social.linkedin")

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
API_VERSION = os.environ.get("LINKEDIN_API_VERSION", "202601")
SCOPES = "openid profile email w_member_social"


def _client_id() -> str:
    v = os.environ.get("LINKEDIN_CLIENT_ID")
    if not v:
        raise SocialPostError("LINKEDIN_CLIENT_ID not configured")
    return v


def _client_secret() -> str:
    v = os.environ.get("LINKEDIN_CLIENT_SECRET")
    if not v:
        raise SocialPostError("LINKEDIN_CLIENT_SECRET not configured")
    return v


def _redirect_uri() -> str:
    v = os.environ.get("LINKEDIN_REDIRECT_URI")
    if not v:
        raise SocialPostError("LINKEDIN_REDIRECT_URI not configured")
    return v


class LinkedInProvider(SocialProvider):
    identifier = "linkedin"
    name = "LinkedIn"
    max_concurrent_jobs = 2
    oauth2 = True

    def generate_auth_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": _client_id(),
            "redirect_uri": _redirect_uri(),
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri or _redirect_uri(),
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_res.raise_for_status()
            tokens = token_res.json()

            userinfo_res = await client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            userinfo_res.raise_for_status()
            profile = userinfo_res.json()

        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "person_urn": f"urn:li:person:{profile['sub']}",
            "name": profile.get("name"),
            "email": profile.get("email"),
            "picture": profile.get("picture"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect("linkedin: no refresh_token on file (app may not have refresh product)")
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                },
            )
        if res.status_code == 400:
            raise NeedsReconnect("linkedin: refresh_token rejected, reconnect required")
        res.raise_for_status()
        tokens = res.json()
        return {
            **credentials,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh),
            "expires_in": tokens.get("expires_in"),
        }

    async def _upload_image(self, image_url: str, credentials: dict[str, Any]) -> Optional[str]:
        access_token = credentials["access_token"]
        person_urn = credentials["person_urn"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_res = await client.post(
                "https://api.linkedin.com/rest/images?action=initializeUpload",
                headers={**headers, "Content-Type": "application/json"},
                json={"initializeUploadRequest": {"owner": person_urn}},
            )
            if init_res.status_code >= 400:
                logger.warning("linkedin image init failed: %s", init_res.text)
                return None
            init_data = init_res.json()["value"]
            upload_url = init_data["uploadUrl"]
            image_urn = init_data["image"]

            img_res = await client.get(image_url)
            img_res.raise_for_status()

            put_res = await client.put(upload_url, content=img_res.content, headers={"Authorization": f"Bearer {access_token}"})
            if put_res.status_code >= 400:
                logger.warning("linkedin image upload failed: %s", put_res.text)
                return None
        return image_urn

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        access_token = credentials["access_token"]
        person_urn = credentials["person_urn"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        settings = settings or {}
        body: dict[str, Any] = {
            "author": person_urn,
            "commentary": content,
            "visibility": "CONNECTIONS" if settings.get("visibility") == "connections" else "PUBLIC",
            "distribution": {
                "feedDistribution": "MAINFEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": settings.get("comment_privacy") == "none",
        }

        if media_urls:
            image_urn = await self._upload_image(media_urls[0], credentials)
            if image_urn:
                body["content"] = {"media": {"altText": "", "id": image_urn}}

        res = await request_with_retry(
            "POST", "https://api.linkedin.com/rest/posts", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise SocialPostError(f"linkedin post failed ({res.status_code}): {res.text}")

        post_urn = res.headers.get("x-restli-id") or res.headers.get("x-linkedin-id", "")
        post_id = post_urn.split(":")[-1] if post_urn else ""
        return {
            "status": "posted",
            "postId": post_urn,
            "releaseURL": f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else "",
        }

    async def comment(self, post_id: str, content: str, credentials: dict[str, Any]) -> dict[str, Any]:
        access_token = credentials["access_token"]
        person_urn = credentials["person_urn"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        res = await request_with_retry(
            "POST",
            f"https://api.linkedin.com/v2/socialActions/{post_id}/comments",
            headers=headers,
            json={"actor": person_urn, "message": {"text": content}},
        )
        if res.status_code >= 400:
            raise SocialPostError(f"linkedin comment failed ({res.status_code}): {res.text}")
        data = res.json()
        comment_id = data.get("$URN", "")
        return {"status": "posted", "postId": comment_id, "releaseURL": ""}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # LinkedIn's engagement-metrics APIs (organizationalEntityShareStatistics,
        # memberShareStatistics) require additional partner-only product access
        # beyond "Share on LinkedIn" — most apps cannot pull real numbers here.
        # Returning zeros rather than faking data until that access exists.
        logger.debug("linkedin analytics for %s: no metrics API access configured", post_id)
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
