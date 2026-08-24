"""Gemini-SDK-shaped compatibility shim over app/core/llm.py (litellm).

Stage 4 of the litellm migration. Both main.py's manual tool-calling loop
(``run_assistant``) and plugins/graph_agent.py's LangGraph state machine are
written directly against the google-genai SDK's shapes:

  - responses: ``response.candidates[0].content.parts``,
    ``part.function_call.name``/``.args``, ``response.text``,
    ``response.model_version``, ``response.usage_metadata``.
  - conversation history: built and mutated as
    ``genai_types.Content(role=..., parts=[...])`` /
    ``genai_types.Part.from_text(...)`` /
    ``genai_types.Part.from_function_response(...)``.

Rather than rewrite either caller, this module presents a drop-in-compatible
surface backed by litellm (via app/core/llm.py's ``complete()``/``stream()``
and its ``to_litellm_messages()``/``parsed_tool_calls()`` converters). Under
the ``KIN_USE_LITELLM`` flag, main.py injects ``gemini_compat.generate`` /
``gemini_compat.types`` wherever it previously injected
``_gemini_generate`` / the real ``genai_types`` — the call signatures and
returned attribute shapes match closely enough that graph_agent.py needs
*zero* internal changes; only what main.py puts into the deps dict changes
identity.

Only mirrors the subset of the google-genai surface main.py and
graph_agent.py actually touch (grepped for `genai_types.`, `.candidates`,
`.function_call`, `.model_version`, `.usage_metadata`, `.thought` before
writing this) — it is NOT a general google-genai replacement. In
particular:

  - ``Part.thought`` is always ``False`` here: litellm's OpenAI-compatible
    surface doesn't expose separate "thinking" parts the way
    ``gemini-2.5-*``'s native SDK response does, so ``_extract_thinking()``
    (main.py) / ``deps["extract_thinking"]`` (graph_agent.py) will always
    return ``""`` for turns that went through this shim. This is a known,
    accepted gap for this stage — flagged in the Stage 4 report, not
    silently swallowed.
  - Inline binary parts (``Part.from_bytes`` — voice-message audio input)
    and ``file_data`` parts are dropped by
    ``app.core.llm.to_litellm_messages`` (see its docstring); audio-message
    turns through KIN_USE_LITELLM are unverified.
  - Retry/fallback is delegated to litellm's own ``num_retries``/
    ``fallbacks`` handling inside ``app.core.llm.complete``/``stream``,
    rather than reimplementing main.py's bespoke transient-error retry loop
    and manual fallback-chain walk. Behaviorally similar, not identical —
    needs live-traffic comparison (see scripts/graph_parity_check.py).
"""
from __future__ import annotations

from typing import Any, Optional

from app.core import llm as llm_core

# ---------------------------------------------------------------------------
# Gemini-shaped value types
# ---------------------------------------------------------------------------


class FunctionCall:
    __slots__ = ("name", "args")

    def __init__(self, name: str, args: Optional[dict] = None):
        self.name = name
        self.args = args or {}


class FunctionResponse:
    __slots__ = ("name", "response")

    def __init__(self, name: str, response: Any):
        self.name = name
        self.response = response


class Part:
    """Mimics ``google.genai.types.Part`` far enough for main.py's and
    graph_agent.py's usage: ``.text``, ``.function_call``,
    ``.function_response``, ``.thought`` (always False — see module
    docstring), plus the ``inline_data``/``file_data`` attributes some
    call sites probe defensively via ``getattr(..., None)``."""

    def __init__(
        self,
        *,
        text: Optional[str] = None,
        function_call: Optional[FunctionCall] = None,
        function_response: Optional[FunctionResponse] = None,
    ):
        self.text = text
        self.function_call = function_call
        self.function_response = function_response
        self.thought = False
        self.inline_data = None
        self.file_data = None

    @classmethod
    def from_text(cls, text: str) -> "Part":
        return cls(text=text)

    @classmethod
    def from_function_response(cls, name: str, response: Any) -> "Part":
        return cls(function_response=FunctionResponse(name=name, response=response))


class Content:
    """Mimics ``google.genai.types.Content``: a mutable ``.role`` +
    ``.parts`` list. Both main.py and graph_agent.py conditionally assign
    ``content.role = "model"`` after the fact when the SDK didn't set one,
    so ``.role`` must stay settable (not a frozen dataclass)."""

    def __init__(self, *, role: Optional[str] = None, parts: Optional[list[Part]] = None):
        self.role = role
        self.parts = parts or []


class GenerateContentConfig:
    """Mirrors only the fields main.py actually sets on the real
    ``genai_types.GenerateContentConfig``: ``system_instruction``,
    ``tools`` (here: an OPENAI_DECLARATIONS-shaped ``list[dict]``, NOT a
    Gemini ``Tool`` object), ``temperature``, ``max_output_tokens``."""

    def __init__(
        self,
        *,
        system_instruction: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ):
        self.system_instruction = system_instruction
        self.tools = tools
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens


class UsageMetadata:
    def __init__(self, prompt_token_count: int = 0, candidates_token_count: int = 0):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class Candidate:
    def __init__(self, content: Optional[Content]):
        self.content = content


class GenerateContentResponse:
    """Mimics the subset of ``google.genai.types.GenerateContentResponse``
    that main.py/graph_agent.py read: ``.candidates``, ``.text``,
    ``.model_version``, ``.usage_metadata``."""

    def __init__(
        self,
        *,
        candidates: list[Candidate],
        text: str,
        model_version: str,
        usage_metadata: UsageMetadata,
        raw: Any = None,
    ):
        self.candidates = candidates
        self.text = text
        self.model_version = model_version
        self.usage_metadata = usage_metadata
        self.raw_litellm_response = raw


class types:  # noqa: N801 — deliberately named/shaped like a module namespace
    """Drop-in stand-in for ``from google.genai import types as genai_types``.

    main.py's tool loop and graph_agent.py only ever reference
    ``genai_types.Content``, ``genai_types.Part``, and (main.py only, for
    building ``config``) ``genai_types.GenerateContentConfig`` — never
    ``Type``/``Schema``/``Tool``/``FunctionDeclaration`` from within the
    loop itself (those live in agent_tools.py, swapped separately for
    ``OPENAI_DECLARATIONS``). So this only needs to cover those three.
    """

    Content = Content
    Part = Part
    GenerateContentConfig = GenerateContentConfig


# ---------------------------------------------------------------------------
# Gemini-shaped call functions, backed by app/core/llm.py
# ---------------------------------------------------------------------------


def _messages_for(contents: list, config: Optional[GenerateContentConfig]) -> list[dict]:
    system_instruction = getattr(config, "system_instruction", None) if config else None
    return llm_core.to_litellm_messages(contents, system_instruction=system_instruction)


def _response_from_result(result: "llm_core.LLMResult") -> GenerateContentResponse:
    calls = llm_core.parsed_tool_calls(result)
    parts: list[Part] = []
    if result.text:
        parts.append(Part.from_text(result.text))
    for c in calls:
        parts.append(Part(function_call=FunctionCall(name=c["name"], args=c["args"])))
    content = Content(role="model", parts=parts) if parts else None
    return GenerateContentResponse(
        candidates=[Candidate(content=content)] if content is not None else [],
        text=result.text,
        model_version=result.model_used,
        usage_metadata=UsageMetadata(result.prompt_tokens, result.completion_tokens),
        raw=result.raw_response,
    )


async def generate(
    *,
    model: str,
    contents: list,
    config: Optional[GenerateContentConfig] = None,
    max_attempts: int = 4,
    feature: str = "agent_loop",
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> GenerateContentResponse:
    """Drop-in replacement for main.py's ``_gemini_generate`` / the
    ``deps["gemini_generate"]`` callable graph_agent.py invokes. Same
    calling convention (``model=``, ``contents=``, ``config=``,
    ``max_attempts=`` — the only kwargs either caller actually passes), same
    returned attribute shape (``.candidates[0].content.parts``, ``.text``,
    ``.model_version``, ``.usage_metadata``)."""
    messages = _messages_for(contents, config)
    result = await llm_core.complete(
        model=model,
        messages=messages,
        tools=(config.tools if config else None),
        temperature=(config.temperature if config else None),
        max_tokens=(config.max_output_tokens if config else None),
        max_attempts=max_attempts,
        feature=feature,
        user_id=user_id,
        turn_id=turn_id,
        message_id=message_id,
    )
    return _response_from_result(result)


async def generate_stream(
    *,
    model: str,
    contents: list,
    config: Optional[GenerateContentConfig] = None,
    on_token=None,
    max_attempts: int = 4,
    feature: str = "agent_loop",
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> dict:
    """Drop-in replacement for main.py's ``_gemini_stream``. Returns the same
    normalized dict shape: ``{text, function_calls, model_content, thinking}``
    (``thinking`` is always ``""`` here — see module docstring). Not
    currently wired into either the manual loop or graph_agent.py (neither
    calls ``_gemini_stream`` today — it's dead code reserved for a future
    streaming endpoint), but provided for parity with app/core/llm.py's new
    ``stream()`` and so a future streaming call site has a ready-made
    KIN_USE_LITELLM counterpart."""
    messages = _messages_for(contents, config)
    result = await llm_core.stream(
        model=model,
        messages=messages,
        tools=(config.tools if config else None),
        on_token=on_token,
        max_attempts=max_attempts,
        feature=feature,
        user_id=user_id,
        turn_id=turn_id,
        message_id=message_id,
    )
    calls = llm_core.parsed_tool_calls(result)
    function_calls = [FunctionCall(name=c["name"], args=c["args"]) for c in calls]
    parts: list[Part] = []
    if result.text and not function_calls:
        parts.append(Part.from_text(result.text))
    parts.extend(Part(function_call=fc) for fc in function_calls)
    model_content = Content(role="model", parts=parts) if parts else None
    return {
        "text": result.text,
        "function_calls": function_calls,
        "model_content": model_content,
        "thinking": "",
    }
