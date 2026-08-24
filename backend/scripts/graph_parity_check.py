"""Live-Gemini parity check between the legacy tool-loop and graph_agent.py.

Runs the SAME prompts through both the manual for-loop (main.run_assistant's
inline logic, reproduced here read-only) and graph_agent's LangGraph state
machine, using the real GEMINI_API_KEY and the real production tool schema
(agent_tools.tool_config()) — but with tool EXECUTION stubbed out (canned
fake results, never touches Supabase or a real user's OAuth tokens). This
proves the two control-flow implementations drive the real model the same
way, without writing anything to production or triggering real side effects.

This is a standalone script, not a pytest test — it makes real, billed
Gemini API calls. Run manually:

    python scripts/graph_parity_check.py

Requires .env's GEMINI_API_KEY. Does NOT require or touch Supabase data.

--- Stage 4 addition: KIN_USE_LITELLM parity mode ---------------------------

Stage 4 of the litellm migration adds a second code path: main.py can now
route the same tool-calling loop through app/core/llm.py (litellm) via the
app/core/gemini_compat.py shim, instead of calling google-genai directly.
Pass --compare-litellm to run every prompt through BOTH:

  1. the Gemini-native path (real genai_client + agent_tools.DECLARATIONS),
     exactly as before, and
  2. the litellm path (app/core/gemini_compat.generate +
     agent_tools.OPENAI_DECLARATIONS),

then diff each pair's reply text, tool-call trace (name + args, in order),
and prompt/completion token counts, printing a clear PASS/FAIL per prompt
and a summary at the end.

This still can't be exercised in a sandbox without network access and a
real GEMINI_API_KEY — it has NOT been run against real credentials as part
of writing this. A human must run `python scripts/graph_parity_check.py
--compare-litellm` against real credentials and eyeball the diffs (small
wording differences in `reply` are expected and fine; differences in WHICH
tool got called, with what arguments, or a large token-count delta are not)
before KIN_USE_LITELLM is trusted in any real environment.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
# agent_tools.py / graph_agent.py are written as top-level modules (they
# import each other and their sibling plugins as `import agent_tools` /
# `from plugins import ...` inconsistently across the codebase) and expect
# plugins/ itself on sys.path, not just the project root.
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "plugins"))

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types as genai_types

import agent_tools
import graph_agent

from app.core import gemini_compat

MODEL_NAME = os.environ.get("KIN_MODEL") or "gemini-2.5-flash-lite"

FAKE_USER = {
    "id": "parity-check-fake-user",
    "google_access_token": "fake-token",
    "microsoft_access_token": None,
    "timezone": "UTC",
    "plan": "pro",
}

SYSTEM_PROMPT = (
    "You are Kin, a personal AI assistant. Today is a test day. "
    "You have tools available for email, calendar, tasks, and contacts. "
    "Call the appropriate tool for any request that needs live data."
)

PROMPTS = [
    "What's on my calendar today?",
    "Check my email for anything from my boss.",
    "What's the weather like?",  # expects no tool call
]

_FAKE_TOOL_RESULTS = {
    "read_gmail": {"emails": [{"subject": "Q3 planning", "from": "boss@company.com", "snippet": "..."}]},
    "read_calendar": {"events": [{"title": "Standup", "start": "09:00"}]},
}


async def _fake_execute_tool(name, args, **kwargs):
    print(f"    [tool call] {name}({args})  <- STUBBED, no real API/DB hit")
    return _FAKE_TOOL_RESULTS.get(name, {"result": "ok (stubbed)"})


def _extract_usage(resp):
    meta = getattr(resp, "usage_metadata", None)
    if not meta:
        return 0, 0
    return (
        getattr(meta, "prompt_token_count", None) or 0,
        getattr(meta, "candidates_token_count", None) or 0,
    )


def _extract_thinking(resp):
    parts = []
    try:
        for candidate in resp.candidates or []:
            for part in candidate.content.parts or []:
                if getattr(part, "thought", False) and part.text:
                    parts.append(part.text.strip())
    except Exception:
        pass
    return "\n\n".join(parts)


async def _gemini_generate(*, model, contents, config, max_attempts=2):
    return await client.aio.models.generate_content(model=model, contents=contents, config=config)


async def run_graph_path(client, prompt: str) -> dict:
    """The pre-Stage-4 path: real genai_client + Gemini-native DECLARATIONS."""
    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[agent_tools.tool_config()],
        temperature=0.2,
    )
    config_final = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + graph_agent._FINAL_NUDGE,
    )
    deps = {
        "gemini_generate": _gemini_generate,
        "extract_usage": _extract_usage,
        "extract_thinking": _extract_thinking,
        "execute_tool": _fake_execute_tool,
        "genai_types": genai_types,
        "model_name": MODEL_NAME,
        "fallback_models": [],
        "sensitive_write_tools": frozenset(),
        "max_tool_rounds": 6,
        "retry_attempts": 2,
        "config": config,
        "config_final": config_final,
        "user": FAKE_USER,
        "supabase": None,
        "genai_client": client,
        "source": "parity-check",
        "session_id": "parity-check",
        "tool_context": None,
        "is_ambiguous_mail_query": False,
        "both_mail_connected": False,
    }
    contents = [genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt)])]
    return await graph_agent.run(deps, contents=contents, user_text=prompt)


async def run_litellm_path(prompt: str) -> dict:
    """Stage 4's new path: app/core/gemini_compat.py (litellm) +
    agent_tools.OPENAI_DECLARATIONS. Same graph_agent.py, same
    _fake_execute_tool stub, same fake user/config shape — only the
    injected gemini_generate/genai_types/tool-schema identities differ,
    exactly as main.py's KIN_USE_LITELLM branch swaps them."""
    config = gemini_compat.types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=agent_tools.OPENAI_DECLARATIONS,
        temperature=0.2,
    )
    config_final = gemini_compat.types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + graph_agent._FINAL_NUDGE,
        tools=agent_tools.OPENAI_DECLARATIONS,
    )
    deps = {
        "gemini_generate": gemini_compat.generate,
        "extract_usage": _extract_usage,
        "extract_thinking": _extract_thinking,
        "execute_tool": _fake_execute_tool,
        "genai_types": gemini_compat.types,
        "model_name": MODEL_NAME,
        "fallback_models": [],
        "sensitive_write_tools": frozenset(),
        "max_tool_rounds": 6,
        "retry_attempts": 2,
        "config": config,
        "config_final": config_final,
        "user": FAKE_USER,
        "supabase": None,
        "genai_client": None,
        "source": "parity-check",
        "session_id": "parity-check-litellm",
        "tool_context": None,
        "is_ambiguous_mail_query": False,
        "both_mail_connected": False,
    }
    contents = [gemini_compat.types.Content(role="user", parts=[gemini_compat.types.Part.from_text(prompt)])]
    return await graph_agent.run(deps, contents=contents, user_text=prompt)


def _tool_calls_signature(tool_trace: list[dict]) -> list[tuple]:
    return [(t.get("tool"), tuple(sorted((t.get("args") or {}).items()))) for t in tool_trace]


def _diff_results(prompt: str, gemini_result: dict, litellm_result: dict) -> list[str]:
    """Returns a list of human-readable mismatch descriptions; empty means
    the two paths agreed closely enough to call it a PASS.

    Reply-text is compared loosely (both non-empty vs both empty, since the
    same model given the same tool schema will not usually produce
    byte-identical prose across two separate calls even on the Gemini-native
    path alone) — the load-bearing checks are which tool(s) got called with
    what arguments, and that token accounting isn't wildly different.
    """
    issues: list[str] = []

    g_reply = (gemini_result.get("reply") or "").strip()
    l_reply = (litellm_result.get("reply") or "").strip()
    if bool(g_reply) != bool(l_reply):
        issues.append(
            f"reply presence differs: gemini={'non-empty' if g_reply else 'EMPTY'!r}, "
            f"litellm={'non-empty' if l_reply else 'EMPTY'!r}"
        )

    g_calls = _tool_calls_signature(gemini_result.get("tool_trace") or [])
    l_calls = _tool_calls_signature(litellm_result.get("tool_trace") or [])
    if g_calls != l_calls:
        issues.append(
            "tool calls differ:\n"
            f"    gemini:  {g_calls}\n"
            f"    litellm: {l_calls}"
        )

    g_usage = gemini_result.get("usage") or {}
    l_usage = litellm_result.get("usage") or {}
    g_total = (g_usage.get("prompt", 0) or 0) + (g_usage.get("completion", 0) or 0)
    l_total = (l_usage.get("prompt", 0) or 0) + (l_usage.get("completion", 0) or 0)
    if g_total and l_total:
        delta_pct = abs(g_total - l_total) / max(g_total, l_total) * 100
        if delta_pct > 40:
            issues.append(
                f"token usage differs by {delta_pct:.0f}% "
                f"(gemini total={g_total}, litellm total={l_total}) — "
                "large deltas can mean the litellm path is sending a "
                "different/duplicated tool schema or history shape, worth a look"
            )
    elif bool(g_total) != bool(l_total):
        issues.append(f"one path reported zero usage: gemini={g_usage}, litellm={l_usage}")

    return issues


async def run_compare(client) -> bool:
    """Runs every PROMPT through both paths, prints a PASS/FAIL report per
    prompt plus a summary. Returns True iff every prompt passed."""
    all_passed = True
    for prompt in PROMPTS:
        print(f"\n=== Prompt: {prompt!r} ===")
        print("  -- gemini-native path --")
        gemini_result = await run_graph_path(client, prompt)
        print(f"    reply: {gemini_result['reply'][:200]}")
        print(f"    tool_trace: {gemini_result['tool_trace']}")
        print(f"    usage: {gemini_result['usage']}")

        print("  -- litellm path --")
        litellm_result = await run_litellm_path(prompt)
        print(f"    reply: {litellm_result['reply'][:200]}")
        print(f"    tool_trace: {litellm_result['tool_trace']}")
        print(f"    usage: {litellm_result['usage']}")

        issues = _diff_results(prompt, gemini_result, litellm_result)
        if issues:
            all_passed = False
            print(f"  >>> FAIL ({len(issues)} issue(s)):")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print("  >>> PASS")

    print("\n" + "=" * 60)
    print("PARITY CHECK: " + ("ALL PROMPTS PASSED" if all_passed else "SOME PROMPTS FAILED — see FAIL entries above"))
    print("=" * 60)
    print(
        "\nReminder: this only checked tool_trace/usage/reply-presence "
        "parity for the fixed PROMPTS list above with tool execution "
        "stubbed out. It does NOT prove: audio-message input works "
        "through the litellm path (known gap — see app/core/llm.py's "
        "to_litellm_messages() docstring), that 'thinking' output parity "
        "holds (gemini_compat.py always returns empty thinking — known "
        "gap), that real (non-stubbed) tool execution round-trips "
        "correctly for tools with array/enum/nested-object arguments, or "
        "that litellm's built-in retry/fallback behaves equivalently to "
        "main.py's bespoke retry loop under real transient errors. Those "
        "need separate, deliberate live-traffic testing before "
        "KIN_USE_LITELLM ships broadly."
    )
    return all_passed


async def main():
    global client
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compare-litellm",
        action="store_true",
        help=(
            "Also run every prompt through the Stage-4 litellm path "
            "(app/core/gemini_compat.py + agent_tools.OPENAI_DECLARATIONS) "
            "and diff against the Gemini-native path. Without this flag, "
            "behaves exactly as before (Gemini-native path only, no diffing)."
        ),
    )
    args = parser.parse_args()

    if args.compare_litellm:
        passed = await run_compare(client)
        sys.exit(0 if passed else 1)

    for prompt in PROMPTS:
        print(f"\n=== Prompt: {prompt!r} ===")
        result = await run_graph_path(client, prompt)
        print(f"  reply: {result['reply'][:200]}")
        print(f"  tool_trace: {result['tool_trace']}")
        print(f"  usage: {result['usage']}")


if __name__ == "__main__":
    asyncio.run(main())
