"""Basic test suite for kin-voice-worker.

Covers the pure/testable surface of worker.py: provider-selection factory
functions (build_llm/build_stt/build_tts/build_realtime), the Azure
"region:key" parsing helper, the tool schema catalogue, and the
kin-backend HTTP client helpers (via a mocked transport — no real network
calls or LiveKit connection needed).
"""
import asyncio
import json as _json

import httpx
import pytest

import worker


# ---------------------------------------------------------------------------
# _split_azure_key
# ---------------------------------------------------------------------------

def test_split_azure_key_valid():
    region, key = worker._split_azure_key("eastus:abcd1234")
    assert region == "eastus"
    assert key == "abcd1234"


def test_split_azure_key_key_contains_colon():
    # partition splits on the FIRST colon only, so a key that itself
    # contains a colon is preserved intact.
    region, key = worker._split_azure_key("eastus:abcd:1234")
    assert region == "eastus"
    assert key == "abcd:1234"


def test_split_azure_key_missing_colon_raises():
    with pytest.raises(ValueError):
        worker._split_azure_key("no-colon-here")


def test_split_azure_key_empty_raises():
    with pytest.raises(ValueError):
        worker._split_azure_key("")


# ---------------------------------------------------------------------------
# build_llm / build_stt / build_tts / build_realtime — unsupported providers
# ---------------------------------------------------------------------------

def test_build_llm_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported llm_provider"):
        worker.build_llm("not-a-real-provider", "some-model", "key")


def test_build_stt_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported stt_provider"):
        worker.build_stt("not-a-real-provider", "key")


def test_build_tts_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported tts_provider"):
        worker.build_tts("not-a-real-provider", None, "key")


def test_build_realtime_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported realtime provider"):
        worker.build_realtime("not-a-real-provider", "model", None, "key")


# ---------------------------------------------------------------------------
# build_stt / build_tts — Google requires a service-account JSON, not a
# plain API key string
# ---------------------------------------------------------------------------

def test_build_stt_google_without_api_key_raises():
    with pytest.raises(ValueError, match="service-account JSON"):
        worker.build_stt("google", None)


def test_build_tts_google_without_api_key_raises():
    with pytest.raises(ValueError, match="service-account JSON"):
        worker.build_tts("google", None, None)


# ---------------------------------------------------------------------------
# build_llm / build_stt / build_tts — supported providers construct without
# raising (construction only stores the key; it doesn't make a network call)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", ["openai", "anthropic", "google", "xai"])
def test_build_llm_supported_providers_construct(provider):
    llm = worker.build_llm(provider, "test-model", "test-key")
    assert llm is not None


@pytest.mark.parametrize("provider", ["deepgram", "assemblyai", "openai"])
def test_build_stt_supported_providers_construct(provider):
    stt = worker.build_stt(provider, "test-key")
    assert stt is not None


def test_build_stt_azure_constructs():
    stt = worker.build_stt("azure", "eastus:test-key")
    assert stt is not None


@pytest.mark.parametrize("provider", ["elevenlabs", "cartesia", "rime", "lmnt"])
def test_build_tts_supported_providers_construct(provider):
    tts = worker.build_tts(provider, None, "test-key")
    assert tts is not None


def test_build_tts_azure_constructs():
    tts = worker.build_tts("azure", None, "eastus:test-key")
    assert tts is not None


# ---------------------------------------------------------------------------
# AVAILABLE_TOOL_SCHEMAS — structural sanity
# ---------------------------------------------------------------------------

def test_tool_schemas_have_required_fields():
    for tool_name, schema in worker.AVAILABLE_TOOL_SCHEMAS.items():
        assert schema["name"] == tool_name
        assert isinstance(schema["description"], str) and schema["description"]
        params = schema["parameters"]
        assert params["type"] == "object"
        properties = params["properties"]
        for required_field in params.get("required", []):
            assert required_field in properties, (
                f"{tool_name}: required field {required_field!r} missing from properties"
            )


# ---------------------------------------------------------------------------
# build_tools — unknown tool names are skipped, known ones are included
# ---------------------------------------------------------------------------

def test_build_tools_skips_unknown_and_keeps_known():
    known = next(iter(worker.AVAILABLE_TOOL_SCHEMAS))
    tools = worker.build_tools("voice-agent-id", [known, "totally_unknown_tool"])
    assert len(tools) == 1


def test_build_tools_empty_list_returns_empty():
    assert worker.build_tools("voice-agent-id", []) == []


# ---------------------------------------------------------------------------
# kin-backend HTTP helpers — verified against a mocked transport, no real
# network call and no live kin-backend needed.
# ---------------------------------------------------------------------------

def _fake_backend_client(handler):
    """Build a _backend_client() replacement wired to a mocked transport —
    no real network call, no live kin-backend needed."""
    def factory():
        return httpx.AsyncClient(
            base_url=worker.KIN_BACKEND_URL,
            timeout=20.0,
            headers={"Authorization": f"Bearer {worker.FUNCTION_SECRET}"},
            transport=httpx.MockTransport(handler),
        )
    return factory


def test_fetch_voice_agent_config_sends_bearer_auth(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth_header"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "va-1", "persona": "hi"})

    monkeypatch.setattr(worker, "_backend_client", _fake_backend_client(handler))

    config = asyncio.run(worker.fetch_voice_agent_config("va-1"))

    assert config == {"id": "va-1", "persona": "hi"}
    assert captured["url"].endswith("/internal/voice-agents/va-1/config")
    assert captured["auth_header"] == f"Bearer {worker.FUNCTION_SECRET}"


def test_report_call_event_drops_none_fields(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "call-1"})

    monkeypatch.setattr(worker, "_backend_client", _fake_backend_client(handler))

    result = asyncio.run(
        worker.report_call_event(
            voice_agent_id="va-1", direction="inbound", from_number=None, to_number="+1555"
        )
    )

    assert result == {"id": "call-1"}
    sent = _json.loads(captured["body"])
    assert "from_number" not in sent
    assert sent["to_number"] == "+1555"
    assert sent["voice_agent_id"] == "va-1"


def test_execute_backend_tool_posts_expected_payload(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        return httpx.Response(200, json={"result": "ok"})

    monkeypatch.setattr(worker, "_backend_client", _fake_backend_client(handler))

    result = asyncio.run(worker.execute_backend_tool("va-1", "create_lead", {"name": "Alice"}))

    assert result == {"result": "ok"}
    assert captured["url"].endswith("/internal/voice-tools/execute")
    sent = _json.loads(captured["body"])
    assert sent == {"voice_agent_id": "va-1", "tool_name": "create_lead", "args": {"name": "Alice"}}
