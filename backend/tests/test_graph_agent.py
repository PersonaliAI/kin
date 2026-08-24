"""Pure unit tests for graph_agent.py's routing logic, using fake Gemini
responses and a fake tool executor — no live API calls, no `main` import.

Verifies the state-machine reproduces the legacy loop's documented behavior:
tool-call round trips, the exceeded-rounds final nudge, and the
not-connected short-circuit. Full behavioral parity against real Gemini
traffic (thought-signature handling, actual model refusal phrasing, etc.)
is NOT covered here and must be verified separately before KIN_USE_LANGGRAPH
is enabled against production traffic.
"""
import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types as genai_types

from plugins import graph_agent


def _text_response(text: str, model="gemini-test"):
    part = SimpleNamespace(text=text, function_call=None, thought=False)
    content = SimpleNamespace(role="model", parts=[part])
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(
        candidates=[candidate], text=text, usage_metadata=None, model_version=model,
    )


def _tool_call_response(name: str, args: dict, model="gemini-test"):
    fc = SimpleNamespace(name=name, args=args)
    part = SimpleNamespace(text=None, function_call=fc, thought=False)
    content = SimpleNamespace(role="model", parts=[part])
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(
        candidates=[candidate], text="", usage_metadata=None, model_version=model,
    )


def _base_deps(gemini_generate, execute_tool):
    return {
        "gemini_generate": gemini_generate,
        "extract_usage": lambda r: (0, 0),
        "extract_thinking": lambda r: "",
        "execute_tool": execute_tool,
        "genai_types": genai_types,
        "model_name": "gemini-test",
        "fallback_models": [],
        "sensitive_write_tools": frozenset(),
        "max_tool_rounds": 3,
        "retry_attempts": 1,
        "config": SimpleNamespace(),
        "config_final": SimpleNamespace(),
        "user": {"id": "u1"},
        "supabase": None,
        "genai_client": None,
        "source": "web",
        "session_id": "s1",
        "tool_context": None,
        "is_ambiguous_mail_query": False,
        "both_mail_connected": False,
    }


def test_direct_text_reply_no_tools():
    async def gemini_generate(**kwargs):
        return _text_response("Hello there!")

    async def execute_tool(*a, **kw):
        raise AssertionError("should not be called")

    deps = _base_deps(gemini_generate, execute_tool)
    result = asyncio.run(graph_agent.run(deps, contents=[], user_text="hi"))
    assert result["reply"] == "Hello there!"
    assert result["tool_trace"] == []


def test_single_tool_round_trip():
    calls = {"n": 0}

    async def gemini_generate(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _tool_call_response("read_gmail", {"query": ""})
        return _text_response("You have 3 unread emails.")

    async def execute_tool(name, args, **kw):
        assert name == "read_gmail"
        return {"emails": []}

    deps = _base_deps(gemini_generate, execute_tool)
    result = asyncio.run(graph_agent.run(deps, contents=[], user_text="check my email"))
    assert result["reply"] == "You have 3 unread emails."
    assert result["tool_trace"] == [{"tool": "read_gmail", "args": {"query": ""}, "round": 0}]


def test_not_connected_short_circuits_to_reply():
    async def gemini_generate(**kwargs):
        return _tool_call_response("read_outlook", {})

    async def execute_tool(name, args, **kw):
        return {"error": "Microsoft not connected"}

    deps = _base_deps(gemini_generate, execute_tool)
    result = asyncio.run(graph_agent.run(deps, contents=[], user_text="check outlook"))
    assert "Microsoft" in result["reply"]
    assert "dashboard/integrations" in result["reply"]


def test_exceeded_rounds_hits_final_nudge():
    async def gemini_generate(**kwargs):
        # config_final is a distinct SimpleNamespace() instance from config;
        # use that to detect the final-nudge call specifically.
        if kwargs["config"] is deps["config_final"]:
            return _text_response("Here's what I found so far.")
        return _tool_call_response("read_gmail", {"query": ""})

    async def execute_tool(name, args, **kw):
        return {"emails": []}

    deps = _base_deps(gemini_generate, execute_tool)
    result = asyncio.run(graph_agent.run(deps, contents=[], user_text="check my email"))
    assert result["reply"] == "Here's what I found so far."
    assert len(result["tool_trace"]) == deps["max_tool_rounds"]


def test_fallback_model_blocks_sensitive_write():
    async def gemini_generate(**kwargs):
        return _tool_call_response("send_email", {"to": "x@y.com"}, model="gemini-fallback")

    async def execute_tool(*a, **kw):
        raise AssertionError("sensitive write must not execute from fallback model")

    deps = _base_deps(gemini_generate, execute_tool)
    deps["fallback_models"] = ["gemini-fallback"]
    deps["sensitive_write_tools"] = frozenset({"send_email"})
    result = asyncio.run(graph_agent.run(deps, contents=[], user_text="send an email"))
    assert "reduced capacity" in result["reply"]
