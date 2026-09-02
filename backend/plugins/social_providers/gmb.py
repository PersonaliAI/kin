"""Google Business Profile (GMB) — its own Google OAuth connection (separate
from the user's primary Google Calendar/Gmail connection in google_integrations.py
so a personal Google account and a business-profile-managing account can
differ). Reuses GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET; needs its own
GMB_REDIRECT_URI registered as an additional redirect URI on the same OAuth
client in Google Cloud Console.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import OAuth2Mixin, SocialPostError, SocialProvider, request_with_retry

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/business.manage"


class GMBProvider(OAuth2Mixin, SocialProvider):
    identifier = "gmb"
    name = "Google Business Profile"
    oauth2 = True

    AUTH_URL = AUTH_URL
    TOKEN_URL = TOKEN_URL
    CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
    CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
    REDIRECT_URI_ENV = "GMB_REDIRECT_URI"
    SCOPES = SCOPES
    EXTRA_AUTH_PARAMS = {"access_type": "offline", "prompt": "consent"}

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        creds = await super().exchange_code(code, redirect_uri)
        async with httpx.AsyncClient(timeout=20.0) as client:
            acct_res = await client.get(
                "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                headers={"Authorization": f"Bearer {creds['access_token']}"},
            )
            if acct_res.status_code < 400:
                accounts = acct_res.json().get("accounts", [])
                if accounts:
                    account_name = accounts[0]["name"]  # "accounts/{id}"
                    creds["account_name"] = account_name
                    loc_res = await client.get(
                        f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations",
                        params={"readMask": "name,title"},
                        headers={"Authorization": f"Bearer {creds['access_token']}"},
                    )
                    if loc_res.status_code < 400:
                        locations = loc_res.json().get("locations", [])
                        if locations:
                            creds["location_name"] = locations[0]["name"]  # "locations/{id}"
                            creds["location_title"] = locations[0].get("title")
        return creds

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        settings = settings or {}
        location = credentials.get("location_name")
        if not location:
            raise SocialPostError("gmb: no business location configured for this account")
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "languageCode": "en-US",
            "summary": content,
            "topicType": "STANDARD",
        }
        if media_urls:
            body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": media_urls[0]}]
        cta_type = settings.get("cta_type")
        if cta_type and cta_type != "NONE":
            action_link: dict[str, Any] = {"actionType": cta_type}
            if settings.get("cta_url"):
                action_link["url"] = settings["cta_url"]
            body["callToAction"] = action_link
        res = await request_with_retry(
            "POST", f"https://mybusiness.googleapis.com/v4/{location}/localPosts", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise SocialPostError(f"gmb post failed ({res.status_code}): {res.text}")
        data = res.json()
        name = data.get("name", "")
        return {"status": "posted", "postId": name, "releaseURL": data.get("searchUrl", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        # GMB's public API doesn't expose per-localPost view/click metrics —
        # only aggregate location "Performance API" insights.
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
