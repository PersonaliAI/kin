"""LangGraph state machine for Kin's tool-calling agent loop.

Structural replacement for the manual ``for round_idx in range(MAX_TOOL_ROUNDS)``
loop in ``main.py:run_assistant``. Every branch here corresponds 1:1 to a named
rule from that loop (empty-candidate retry, fallback-model write guard,
no-tool-call refusal detector, dual-mail-source detector, not-connected
short-circuit, exceeded-rounds final nudge) — nothing new was invented, the
control flow was just made explicit as graph edges instead of nested
if/continue statements.

This module never imports ``main`` — ``genai_client`` and the Gemini
call/tool-execution helpers live there, and main.py is the one importing this
module, so a reverse import would be circular. Instead every external
dependency (the Gemini call function, the tool executor, model/limit
constants, per-request config) is injected via ``GraphDeps`` at graph-build
time, and ``main.py`` builds a fresh graph per request with its own closures.

Feature-flagged: only used when ``KIN_USE_LANGGRAPH`` is truthy. Not yet
wired to the live ``/chat`` endpoint — see main.py's ``/chat/graph`` test
endpoint. Do not point production traffic at this until it's been run against
real Gemini traffic and compared against the legacy loop's tool_trace output.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger("kin.graph_agent")


class LoopState(TypedDict, total=False):
    contents: list
    tool_trace: list[dict]
    thinking_parts: list[str]
    usage: dict[str, int]
    round_idx: int
    mail_retry_forced: bool
    fcs: list
    reply: Optional[str]
    reply_is_final: bool


class GraphDeps(TypedDict):
    gemini_generate: Callable[..., Awaitable[Any]]
    extract_usage: Callable[[Any], tuple]
    extract_thinking: Callable[[Any], str]
    execute_tool: Callable[..., Awaitable[dict]]
    genai_types: Any
    model_name: str
    fallback_models: list
    sensitive_write_tools: frozenset
    max_tool_rounds: int
    retry_attempts: int
    config: Any
    config_final: Any
    user: dict
    supabase: Any
    genai_client: Any
    source: str
    session_id: str
    tool_context: Optional[dict]
    is_ambiguous_mail_query: bool
    both_mail_connected: bool


_EMPTY_CANDIDATE_NUDGE = (
    "Please respond to the user's last message. If you encountered an error "
    "or have no data, explain that to the user. Never leave the user without "
    "a reply."
)

_EMPTY_TEXT_NUDGE = (
    "Your previous response was empty. Please provide a helpful text reply "
    "to the user. Summarize any tool results you received, or explain what "
    "happened."
)

_NO_TOOL_CALL_NUDGE = (
    "STOP. You answered without calling a tool. IGNORE any prior errors in "
    "this conversation — bugs have been fixed since then. Retry the user's "
    "request by calling the right tool NOW with the correct arguments."
)

_REFUSAL_PHRASES = (
    "i cannot access", "i can't access", "i don't have access",
    "i am unable to access", "i'm unable to access",
)
_EMPTY_DATA_PHRASES = (
    "no results", "no data", "nothing found", "couldn't find", "could not find",
)
_TOOL_KEYWORDS = (
    "mail", "email", "inbox", "gmail", "outlook",
    "calendar", "event", "task", "contact",
    "document", "drive", "file", "onedrive", "todo",
    "pdf", "docx", "page", "pages", "indexed",
    "send", "download",
)

_FINAL_NUDGE = (
    "\n\nYou've already gathered enough data. Reply to the user now with a "
    "final answer; do not call any more tools. If you don't have everything "
    "needed to complete the request (e.g. a recipient email address), say "
    "what you found so far and ask the user for exactly what's missing — do "
    "NOT return nothing."
)


def build_graph(deps: GraphDeps, user_text: str):
    genai_types = deps["genai_types"]

    async def call_model(state: LoopState) -> LoopState:
        round_idx = state.get("round_idx", 0)
        usage = dict(state["usage"])

        def _track(resp) -> None:
            p, c = deps["extract_usage"](resp)
            usage["prompt"] += p
            usage["completion"] += c

        contents = state["contents"]
        response = await deps["gemini_generate"](
            model=deps["model_name"], contents=contents, config=deps["config"],
            max_attempts=deps["retry_attempts"],
        )
        _track(response)
        candidate = response.candidates[0] if response.candidates else None

        if not candidate or not candidate.content:
            logger.warning("Empty Gemini response (attempt 1). Retrying with nudge.")
            contents = contents + [genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=_EMPTY_CANDIDATE_NUDGE)],
            )]
            response = await deps["gemini_generate"](
                model=deps["model_name"], contents=contents, config=deps["config"],
                max_attempts=deps["retry_attempts"],
            )
            _track(response)
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                reply = (response.text or "").strip() or (
                    "I'm sorry, I wasn't able to process that. Could you try rephrasing your request?"
                )
                return {
                    **state, "contents": contents, "usage": usage,
                    "reply": reply, "reply_is_final": True,
                }

        thinking_parts = list(state["thinking_parts"])
        th = deps["extract_thinking"](response)
        if th:
            thinking_parts.append(th)

        fcs = [p_.function_call for p_ in (candidate.content.parts or []) if p_.function_call]

        actual_model = getattr(response, "model_version", None) or deps["model_name"]
        is_fallback_model = (
            actual_model != deps["model_name"] and str(actual_model) in deps["fallback_models"]
        )
        if fcs and is_fallback_model:
            risky = [fc for fc in fcs if fc.name in deps["sensitive_write_tools"]]
            if risky:
                logger.warning(
                    "Blocked fallback-model (%s) write call(s): %s",
                    actual_model, [fc.name for fc in risky],
                )
                reply = (
                    "I'm at reduced capacity for a moment and don't want to risk "
                    "getting this wrong — could you send that request again? It'll "
                    "go through properly this time."
                )
                return {
                    **state, "contents": contents, "usage": usage,
                    "thinking_parts": thinking_parts, "reply": reply, "reply_is_final": True,
                }

        content_to_append = candidate.content
        if not getattr(content_to_append, "role", None):
            content_to_append.role = "model"
        contents = contents + [content_to_append]

        if fcs:
            return {
                **state, "contents": contents, "usage": usage,
                "thinking_parts": thinking_parts, "fcs": fcs, "round_idx": round_idx,
                "reply": None, "reply_is_final": False,
            }

        # --- No tool calls this round: run the text-response detectors -----
        reply = (response.text or "").strip()
        reply_lower = reply.lower()
        user_lower = (user_text or "").lower()
        is_refusal = any(p in reply_lower for p in _REFUSAL_PHRASES)
        claims_empty = any(p in reply_lower for p in _EMPTY_DATA_PHRASES)
        mentions_tool = any(k in user_lower for k in _TOOL_KEYWORDS)
        needs_retry = reply and round_idx == 0 and mentions_tool and (is_refusal or claims_empty)

        if needs_retry:
            logger.warning(
                "No-tool-call answer detected on round 0 (refusal=%s, empty=%s).",
                is_refusal, claims_empty,
            )
            contents = contents + [genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=_NO_TOOL_CALL_NUDGE)],
            )]
            return {
                **state, "contents": contents, "usage": usage,
                "thinking_parts": thinking_parts, "fcs": [], "reply": None,
                "reply_is_final": False, "round_idx": round_idx,
            }

        is_ambiguous = deps["is_ambiguous_mail_query"]
        both_connected = deps["both_mail_connected"]
        mail_retry_forced = state.get("mail_retry_forced", False)
        if is_ambiguous and both_connected and not mail_retry_forced and reply:
            called_tools = {t["tool"] for t in state["tool_trace"]}
            missing_calls = []
            if "read_gmail" not in called_tools:
                missing_calls.append("read_gmail(query='', limit=50) for Gmail")
            if "read_outlook" not in called_tools:
                missing_calls.append(
                    "read_outlook(query='', limit=50, max_days_old=<N if time-based>) for Outlook"
                )
            if missing_calls:
                logger.warning(
                    "Ambiguous mail query only checked %d/2 sources — forcing retry for: %s",
                    2 - len(missing_calls), missing_calls,
                )
                nudge = (
                    "STOP. The user asked about mail/inbox without naming a "
                    "provider, and both Gmail and Outlook are connected, but "
                    "you only checked one source. Now call "
                    + " and ".join(missing_calls)
                    + ". Then present BOTH sources in your reply, grouped as "
                    "'📧 Gmail:' and '📬 Outlook:' — if one has no results, say "
                    "so briefly and still show the other."
                )
                contents = contents + [genai_types.Content(
                    role="user", parts=[genai_types.Part.from_text(text=nudge)],
                )]
                return {
                    **state, "contents": contents, "usage": usage,
                    "thinking_parts": thinking_parts, "fcs": [], "reply": None,
                    "reply_is_final": False, "mail_retry_forced": True, "round_idx": round_idx,
                }

        if not reply:
            logger.warning("No text parts in candidate.")
            contents = contents + [genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=_EMPTY_TEXT_NUDGE)],
            )]
            retry_resp = await deps["gemini_generate"](
                model=deps["model_name"], contents=contents, config=deps["config"],
                max_attempts=deps["retry_attempts"],
            )
            _track(retry_resp)
            reply = (retry_resp.text or "").strip() or (
                "I'm sorry, I wasn't able to process that. Could you try again?"
            )

        return {
            **state, "contents": contents, "usage": usage,
            "thinking_parts": thinking_parts, "fcs": [], "reply": reply, "reply_is_final": True,
        }

    async def call_tools(state: LoopState) -> LoopState:
        contents = state["contents"]
        tool_trace = list(state["tool_trace"])
        tool_response_parts = []
        tool_results = []
        round_idx = state.get("round_idx", 0)

        for fc in state["fcs"]:
            args = dict(fc.args) if fc.args else {}
            logger.info("tool call: %s(%s)", fc.name, args)
            result = await deps["execute_tool"](
                fc.name, args,
                user=deps["user"], supabase=deps["supabase"], genai_client=deps["genai_client"],
                context={"source": deps["source"], "session_id": deps["session_id"], **(deps["tool_context"] or {})},
            )
            tool_results.append(result)
            tool_trace.append({"tool": fc.name, "args": args, "round": round_idx})
            tool_response_parts.append(
                genai_types.Part.from_function_response(name=fc.name, response={"result": result})
            )

        not_connected_errors = [
            r for r in tool_results
            if isinstance(r, dict) and "not connected" in str(r.get("error", "")).lower()
        ]
        if not_connected_errors and len(not_connected_errors) == len(tool_results):
            err_msg = not_connected_errors[0].get("error", "")
            if "microsoft" in err_msg.lower():
                reply = (
                    "Your Microsoft account isn't connected yet. Please visit "
                    "/dashboard/integrations to connect your Microsoft 365 account, "
                    "then try again."
                )
            elif "google" in err_msg.lower():
                reply = (
                    "Your Google account isn't connected yet. Please visit "
                    "/dashboard/integrations to connect your Google account, then try again."
                )
            else:
                reply = (
                    "The required service isn't connected yet. Please visit "
                    "/dashboard/integrations to connect it."
                )
            return {**state, "tool_trace": tool_trace, "reply": reply, "reply_is_final": True}

        if tool_response_parts:
            contents = contents + [genai_types.Content(role="user", parts=tool_response_parts)]

        return {
            **state, "contents": contents, "tool_trace": tool_trace,
            "round_idx": round_idx + 1, "fcs": [], "reply": None, "reply_is_final": False,
        }

    async def final_nudge(state: LoopState) -> LoopState:
        final = await deps["gemini_generate"](
            model=deps["model_name"], contents=state["contents"], config=deps["config_final"],
            max_attempts=deps["retry_attempts"],
        )
        p, c = deps["extract_usage"](final)
        usage = dict(state["usage"])
        usage["prompt"] += p
        usage["completion"] += c
        contents = state["contents"]

        if not (final.text or "").strip():
            contents = contents + [genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=(
                    "Your previous response was empty. You MUST reply with plain "
                    "text now — summarize what you found and ask the user for "
                    "whatever's missing to finish the request."
                ))],
            )]
            final = await deps["gemini_generate"](
                model=deps["model_name"], contents=contents, config=deps["config_final"],
                max_attempts=deps["retry_attempts"],
            )
            p2, c2 = deps["extract_usage"](final)
            usage["prompt"] += p2
            usage["completion"] += c2

        thinking_parts = list(state["thinking_parts"])
        th = deps["extract_thinking"](final)
        if th:
            thinking_parts.append(th)

        reply = (final.text or "").strip() or (
            "I'm sorry, I wasn't able to complete that request. Could you try again?"
        )
        return {
            **state, "contents": contents, "usage": usage, "thinking_parts": thinking_parts,
            "reply": reply, "reply_is_final": True,
        }

    def route_after_model(state: LoopState) -> str:
        if state.get("reply_is_final"):
            return END
        if state.get("fcs"):
            return "tools"
        return "model"  # nudge/detector loop-back with no new fcs

    def route_after_tools(state: LoopState) -> str:
        if state.get("reply_is_final"):
            return END
        if state.get("round_idx", 0) >= deps["max_tool_rounds"]:
            return "final_nudge"
        return "model"

    graph = StateGraph(LoopState)
    graph.add_node("model", call_model)
    graph.add_node("tools", call_tools)
    graph.add_node("final_nudge", final_nudge)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", route_after_model, {"model": "model", "tools": "tools", END: END})
    graph.add_conditional_edges("tools", route_after_tools, {"model": "model", "final_nudge": "final_nudge", END: END})
    graph.add_edge("final_nudge", END)
    # config's recursion_limit is the graph-level backstop; round_idx-based
    # routing above is the semantic one that mirrors MAX_TOOL_ROUNDS exactly.
    return graph.compile()


async def run(deps: GraphDeps, *, contents: list, user_text: str) -> dict:
    """Runs the graph to completion and returns the same shape run_assistant's
    legacy loop returns: {reply, thinking, tool_trace, usage}."""
    app = build_graph(deps, user_text)
    initial: LoopState = {
        "contents": contents,
        "tool_trace": [],
        "thinking_parts": [],
        "usage": {"prompt": 0, "completion": 0},
        "round_idx": 0,
        "mail_retry_forced": False,
        "fcs": [],
        "reply": None,
        "reply_is_final": False,
    }
    # +4 headroom over max_tool_rounds*2 for the nudge/detector retries that
    # share a round without necessarily reaching "tools" first.
    result = await app.ainvoke(initial, config={"recursion_limit": deps["max_tool_rounds"] * 4 + 10})
    return {
        "reply": result.get("reply") or "I'm sorry, I wasn't able to complete that request. Could you try again?",
        "thinking": "\n\n".join(result.get("thinking_parts", [])),
        "tool_trace": result.get("tool_trace", []),
        "usage": result.get("usage", {"prompt": 0, "completion": 0}),
    }
