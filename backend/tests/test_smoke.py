"""Smoke + pure-logic tests for the Kin backend.

These import the whole app (catching syntax/import breaks — the backend
equivalent of a failed build) and exercise the security- and billing-critical
pure helpers that must never silently regress.
"""
import main
from fastapi.testclient import TestClient


def test_app_imports():
    assert main.app is not None


def test_health_endpoint():
    client = TestClient(main.app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_plan_for_falls_back_to_free():
    assert main.plan_for({}) == "free"
    assert main.plan_for({"plan": "PRO"}) == "pro"
    assert main.plan_for({"plan": "nonsense"}) == "free"


def test_plan_quotas_are_positive():
    for tier in ("free", "basic", "pro", "executive"):
        assert main.PLAN_QUOTAS[tier] > 0


def test_api_key_hash_is_stable_and_sha256():
    assert main._hash_api_key("abc") == main._hash_api_key("abc")
    assert main._hash_api_key("abc") != main._hash_api_key("abd")
    assert len(main._hash_api_key("abc")) == 64
