"""Shared abstraction for social-platform providers (Postiz equivalent).

Mirrors the shape of Postiz's SocialAbstract/SocialProvider interface
(libraries/nestjs-libraries/src/integrations/social in postiz-app) but adapted
to Kin's sync-config/async-call style already used by google_integrations.py
and microsoft_integrations.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("kin.social")


class NeedsReconnect(Exception):
    """Credentials are unusable and cannot be silently refreshed — the user
    must reconnect the integration (e.g. refresh token revoked)."""


class SocialPostError(Exception):
    """A publish/comment/analytics call failed in a way that should mark the
    post 'failed' rather than being retried."""


class SocialProvider(ABC):
    """One instance per platform. Stateless — all per-user state (tokens)
    flows through the `credentials` dict passed into each call, matching how
    Kin already stores decrypted user_credentials payloads."""

    #: how many concurrent publish calls are safe for this platform (mirrors
    #: Postiz's per-provider maxConcurrentJob, e.g. X = 1 due to strict limits)
    max_concurrent_jobs: int = 3

    @property
    @abstractmethod
    def identifier(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    #: True if this platform is connected via an OAuth2 redirect flow
    #: (generate_auth_url/exchange_code/refresh_token). False for platforms
    #: connected via a manual form (app password, bot token, instance URL,
    #: API key) — see connect_manual().
    oauth2: bool = True

    #: True if this provider needs PKCE (RFC 7636) on top of the standard
    #: authorization-code flow — main.py generates a verifier/challenge pair
    #: per connect attempt, stores the verifier in the signed state JWT (so
    #: it survives the redirect round-trip statelessly), and passes
    #: pkce_challenge/pkce_verifier into generate_auth_url/exchange_code.
    uses_pkce: bool = False

    #: True if comment() is actually implemented (posts a reply to a parent
    #: post on the real platform) rather than raising NotImplementedError.
    #: Drives whether the composer's "Add Comment" control is offered for
    #: this platform — see social.py's /api/social/integrations.
    supports_comment: bool = False

    #: True if mention() does a real @-mention lookup rather than returning
    #: an empty list. Most platforms don't expose a public user-search API
    #: to third-party apps (Instagram/Facebook/LinkedIn all lock this down),
    #: so this is opt-in per provider rather than assumed.
    supports_mention: bool = False

    def generate_auth_url(self, state: str, pkce_challenge: Optional[str] = None) -> str:
        raise NotImplementedError(f"{self.identifier} does not support OAuth2 redirect connect")

    async def exchange_code(
        self, code: str, redirect_uri: str, pkce_verifier: Optional[str] = None
    ) -> dict[str, Any]:
        """Exchange an OAuth2 authorization code for a credentials payload.
        Returned dict is stored (Fernet-encrypted) as-is in user_credentials
        and passed back verbatim as `credentials` to post()/comment()/etc."""
        raise NotImplementedError(f"{self.identifier} does not support OAuth2 redirect connect")

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Return an updated credentials payload with a fresh access token.
        Raise NeedsReconnect if the refresh token itself is invalid/expired."""
        raise NeedsReconnect(f"{self.identifier} tokens cannot be refreshed; reconnect required")

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        """For non-OAuth2 platforms: validate a user-submitted form (app
        password, bot token, instance URL, API key, ...) and return the
        credentials payload to store. Should raise SocialPostError with a
        user-facing message on invalid input."""
        raise NotImplementedError(f"{self.identifier} does not support manual connect")

    @abstractmethod
    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Publish a post. `settings` carries optional per-post, per-platform
        options (e.g. privacy level, allow-comments) — providers that don't
        have anything to honor from it can just ignore the argument.
        Returns {"postId": ..., "releaseURL": ...}."""

    async def comment(self, post_id: str, content: str, credentials: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.identifier} does not support comments")

    async def mention(self, query: str, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        """@-mention autocomplete search. Returns matches as
        {"id", "username", "name", "avatarUrl"}. Default: no results —
        overridden only by providers whose platform exposes a real user
        search API (see supports_mention)."""
        return []

    @abstractmethod
    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Returns {"impressions", "likes", "reposts", "comments", "clicks"}."""


def env_or_error(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SocialPostError(f"{name} not configured")
    return v


def generate_pkce_pair() -> tuple[str, str]:
    """RFC 7636 code_verifier / code_challenge (S256) pair. Stateless — no
    caller needs to hold onto anything except passing the verifier through
    (main.py stores it in the signed OAuth state JWT)."""
    import base64
    import hashlib
    import secrets

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class OAuth2Mixin:
    """Standard authorization-code OAuth2 flow, shared by the majority of
    platforms (Reddit, Discord, Slack, Pinterest, Dribbble, Tumblr, Threads,
    TikTok, GMB, YouTube, VK, Kick, Twitch, ...). Subclasses set the class
    attributes below and get generate_auth_url/exchange_code/refresh_token
    for free; post()/comment()/fetch_analytics() are still per-platform.

    CLIENT_ID_ENV / CLIENT_SECRET_ENV / REDIRECT_URI_ENV name the env vars
    holding the app's OAuth client id/secret/redirect URI (matching the
    per-provider env var convention already used for Google/Microsoft/
    LinkedIn in this codebase).
    """

    AUTH_URL: str = ""
    TOKEN_URL: str = ""
    CLIENT_ID_ENV: str = ""
    CLIENT_SECRET_ENV: str = ""
    REDIRECT_URI_ENV: str = ""
    SCOPES: str = ""
    #: extra static query params merged into the auth URL (e.g. response_type
    #: overrides, duration=permanent for Reddit, etc.)
    EXTRA_AUTH_PARAMS: dict[str, str] = {}
    #: True if the token endpoint expects Basic auth (client_id:client_secret)
    #: instead of client_id/client_secret in the POST body (Reddit does this).
    BASIC_AUTH_TOKEN: bool = False

    def generate_auth_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": env_or_error(self.CLIENT_ID_ENV),
            "redirect_uri": env_or_error(self.REDIRECT_URI_ENV),
            "scope": self.SCOPES,
            "state": state,
            **self.EXTRA_AUTH_PARAMS,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        auth = None
        if self.BASIC_AUTH_TOKEN:
            auth = (env_or_error(self.CLIENT_ID_ENV), env_or_error(self.CLIENT_SECRET_ENV))
        else:
            data = {
                **data,
                "client_id": env_or_error(self.CLIENT_ID_ENV),
                "client_secret": env_or_error(self.CLIENT_SECRET_ENV),
            }
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(self.TOKEN_URL, data=data, headers=headers, auth=auth)
        if res.status_code >= 400:
            raise SocialPostError(f"{self.identifier} token request failed ({res.status_code}): {res.text}")
        return res.json()

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        tokens = await self._token_request({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or env_or_error(self.REDIRECT_URI_ENV),
        })
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type", "Bearer"),
        }

    async def refresh_token(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise NeedsReconnect(f"{self.identifier}: no refresh_token on file")
        try:
            tokens = await self._token_request({"grant_type": "refresh_token", "refresh_token": refresh})
        except SocialPostError as e:
            raise NeedsReconnect(str(e))
        return {
            **credentials,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh),
            "expires_in": tokens.get("expires_in"),
        }


async def request_with_retry(
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    backoff_seconds: float = 5.0,
    **kwargs: Any,
) -> httpx.Response:
    """Small reimplementation of Postiz's SocialAbstract.fetch() retry wrapper
    (3 attempts, fixed backoff) for 429/5xx responses. No new dependency —
    plain httpx + asyncio.sleep."""
    last_exc: Optional[Exception] = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                res = await client.request(method, url, **kwargs)
                if res.status_code == 429 or res.status_code >= 500:
                    if attempt < max_attempts:
                        logger.warning(
                            "social provider %s %s -> %s, retrying (%d/%d)",
                            method, url, res.status_code, attempt, max_attempts,
                        )
                        await asyncio.sleep(backoff_seconds)
                        continue
                return res
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_seconds)
                    continue
    assert last_exc is not None
    raise last_exc
