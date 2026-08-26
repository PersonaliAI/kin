"""Shared SSRF guard.

Several features let an authenticated (or, in one now-disabled case, even
unauthenticated) caller supply a URL that this backend then fetches
server-side: the RSS auto-post cron job, MCP server connect/test, the
OpenAPI-spec fetch behind integration publishing, and outbound webhook
registration (Kin webhooks + social webhooks). None of these validated the
target beyond an optional "https://" prefix check, so a caller could point
any of them at an internal/private address (169.254.169.254 metadata
services, localhost, RFC1918 ranges, other internal Cloud Run services) and
use this backend as a proxy to probe or reach them. This module is the one
place that decision lives now — see the security audit report for the full
list of call sites this was wired into.

Residual risk (documented, not fixed here): this validates the hostname's
resolved address at call time, and re-validates every redirect hop before
following it — but does not pin the DNS resolution used for validation to
the one actually used for the TCP connection, so a sufctively-timed
DNS-rebinding attack (the name resolves to a public IP during our check,
then to a private one microseconds later when the HTTP client's own
resolver runs) — a precisely-timed DNS-rebinding attack — is not closed by
this alone. Closing that fully requires
controlling the transport's connection-level socket (e.g. a custom httpx
transport that connects directly to the IP the guard validated), which was
judged too large a change for this pass — flagged as a follow-up.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx

# Hostnames that resolve fine but are always internal-service-shaped, worth
# denying by name even before a DNS lookup.
_DENIED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata"}

DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB — plenty for an RSS feed or an OpenAPI spec


class UnsafeURLError(ValueError):
    """Raised when a URL is not allowed to be fetched server-side."""


def _is_disallowed_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -> deny
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Raise UnsafeURLError unless `url` is a plain http(s) URL whose
    hostname resolves ONLY to public IP addresses. Call before fetching any
    user-supplied URL server-side, and again on every redirect hop (see
    safe_get below)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"unsupported URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no hostname")
    if host.lower() in _DENIED_HOSTNAMES:
        raise UnsafeURLError(f"host not allowed: {host!r}")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"could not resolve host {host!r}: {exc}") from exc
    if not infos:
        raise UnsafeURLError(f"host {host!r} did not resolve to any address")
    for info in infos:
        ip_str = info[4][0]
        if _is_disallowed_ip(ip_str):
            raise UnsafeURLError(f"host {host!r} resolves to a disallowed address ({ip_str})")


async def safe_get(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: float = 10.0,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> httpx.Response:
    """SSRF-guarded GET: validates the URL, follows redirects manually
    (re-validating each hop before following it — closes the classic "safe
    URL that 302s to an internal address" bypass), and caps response size."""
    assert_safe_url(url)
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        for _ in range(max_redirects + 1):
            async with client.stream("GET", current, headers=headers) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        return resp
                    current = str(httpx.URL(current).join(location))
                    assert_safe_url(current)
                    continue

                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise UnsafeURLError(f"response exceeds {max_bytes} byte cap")

                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        raise UnsafeURLError(f"response exceeds {max_bytes} byte cap")
                # Rebuild a non-streaming Response so callers can use
                # .text/.json()/.status_code normally.
                return httpx.Response(
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=body,
                    request=resp.request,
                )
        raise UnsafeURLError("too many redirects")
