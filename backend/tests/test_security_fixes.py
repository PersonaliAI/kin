"""Regression tests for the security-audit remediation pass:
  * verify_shared_secret / require_shared_secret (FUNCTION_SECRET gating:
    constant-time compare + fail-closed when unset).
  * _client_ip (X-Forwarded-For spoofing fix — trust the last hop, not the
    first).
"""
from fastapi import HTTPException, Request
import pytest

from app.core import security as sec


def test_verify_shared_secret_matches():
    assert sec.verify_shared_secret("s3cret", "s3cret") is True


def test_verify_shared_secret_mismatch():
    assert sec.verify_shared_secret("wrong", "s3cret") is False


def test_verify_shared_secret_fails_closed_when_unconfigured():
    # The old `if FUNCTION_SECRET and secret != FUNCTION_SECRET` pattern
    # skipped the check entirely (fail-OPEN) when the configured secret was
    # empty/unset. Any provided value — even an empty one — must be denied.
    assert sec.verify_shared_secret("anything", "") is False
    assert sec.verify_shared_secret("", "") is False
    assert sec.verify_shared_secret(None, "") is False


def test_verify_shared_secret_denies_missing_provided_value():
    assert sec.verify_shared_secret(None, "s3cret") is False
    assert sec.verify_shared_secret("", "s3cret") is False


def test_require_shared_secret_raises_403_on_mismatch():
    with pytest.raises(HTTPException) as exc_info:
        sec.require_shared_secret("wrong", "s3cret")
    assert exc_info.value.status_code == 403


def test_require_shared_secret_raises_403_when_unconfigured():
    with pytest.raises(HTTPException) as exc_info:
        sec.require_shared_secret("whatever", "")
    assert exc_info.value.status_code == 403


def test_require_shared_secret_passes_on_match():
    sec.require_shared_secret("s3cret", "s3cret")  # must not raise


def _make_request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("203.0.113.9", 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def test_client_ip_trusts_last_xff_hop_not_first():
    # Cloud Run's own front end appends the real client IP as the LAST
    # entry; earlier entries can be set by the client itself. Previously
    # this took the FIRST entry, letting any caller spoof their apparent IP.
    request = _make_request({"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.9.9.9"})
    assert sec._client_ip(request) == "9.9.9.9"
    assert sec.client_ip(request) == "9.9.9.9"


def test_client_ip_falls_back_to_socket_peer_without_xff():
    request = _make_request({})
    assert sec._client_ip(request) == "203.0.113.9"
