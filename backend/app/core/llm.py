"""Unified LLM-calling module, built on litellm.

Stage 0/1 of a staged migration off direct google-genai calls in main.py
(``_gemini_generate``). This module is additive — main.py still owns the
streaming/tool-calling path for now. Only the non-streaming, non-tool-calling
single-shot path (app/routers/prompt_tuning.py) has been migrated to prove
the module works end-to-end.

# TODO(stage-2): streaming support (litellm.acompletion(stream=True)).
# TODO(stage-3, partial): plugins/doc_rag.py's vision-OCR call site
#   (ocr_image) now goes through this module using OpenAI-style multimodal
#   ``messages`` content lists; ``response_format`` was added for
#   schema-constrained JSON output. Tool-calling / function-call translation
#   to and from the Gemini-native genai_types.Content/Part shape used by
#   main.py's run_assistant tool loop is still outstanding.
# Stage 5: BYOK (per-user API keys) support via complete()'s optional
#   ``api_key`` override, plus embeddings (litellm.aembedding) for
#   plugins/memory.py's text-embedding-004 usage.
#
# Stage 4 addendum: added ``stream()`` plus ``to_litellm_messages()`` /
# ``parsed_tool_calls()`` conversion helpers so main.py's tool-calling agent
# loop (and plugins/graph_agent.py) can be migrated behind the
# ``KIN_USE_LITELLM`` flag. See app/core/gemini_compat.py for the
# Gemini-SDK-shaped adapter built on top of these that the tool loop
# actually consumes — that module exists because both main.py's manual loop
# and graph_agent.py are written directly against google-genai's
# response/content shapes (candidate.content.parts, part.function_call,
# response.model_version, genai_types.Content/Part construction), not just
# against this module's OpenAI-shaped messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import litellm

from app.core.clients import supabase
from app.core.config import GEMINI_API_KEY, GOOGLE_CLOUD_LOCATION, GOOGLE_CLOUD_PROJECT

logger = logging.getLogger("kin")

# Default embedding model for embed() when the caller doesn't specify one.
# plugins/memory.py passes its own KIN_EMBED_MODEL-derived model explicitly,
# so this default mostly matters for future/other call sites.
EMBED_MODEL_DEFAULT = os.environ.get("KIN_EMBED_MODEL", "text-embedding-004")

# Same default chain as main.py's GEMINI_FALLBACK_MODELS, re-parsed here
# rather than imported to avoid a circular import (main.py will eventually
# import from this module).
_FALLBACK_MODELS: list[str] = [
    m.strip() for m in os.environ.get(
        "KIN_FALLBACK_MODELS",
        "gemini-2.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3-flash",
    ).split(",") if m.strip()
]


@dataclass
class LLMResult:
    text: str
    function_calls: list = field(default_factory=list)
    raw_response: Any = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Optional[float] = None
    model_used: str = ""
    is_fallback: bool = False


def _provider_prefix() -> str:
    """'gemini' (AI Studio billing) if GEMINI_API_KEY is set, else 'vertex_ai'."""
    return "gemini" if GEMINI_API_KEY else "vertex_ai"


def _litellm_model(model: str) -> str:
    return f"{_provider_prefix()}/{model}"


async def complete(
    *,
    model: str,
    messages: list[dict],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools=None,
    response_format: Optional[dict] = None,
    max_attempts: int = 4,
    feature: str,
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMResult:
    """Single-turn, non-streaming chat completion via litellm.

    ``messages`` is the plain OpenAI chat-message shape:
    ``[{"role": "user"/"system"/"assistant", "content": str}, ...]``.
    Content may be a plain string, or (for vision input) a list of
    OpenAI-style content parts, e.g.::

        [{"type": "text", "text": "..."},
         {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}]

    litellm translates the ``image_url`` part into Gemini's native inline-data
    image format automatically — no extra params are needed on this function
    for vision; just build the message content list this way.

    ``response_format`` (stage-3 addition) enables structured/schema-constrained
    JSON output. Pass the OpenAI-style shape, e.g.::

        {"type": "json_schema", "json_schema": {"name": "...", "schema": {...}}}

    litellm forwards this to Gemini's ``response_mime_type``/``response_schema``
    under the hood. Omit it (the default) for plain-text completions — this
    keeps the three existing call sites (app/routers/prompt_tuning.py,
    app/routers/social.py, main.py's _get_rolling_summary) unaffected.

    ``api_key`` (stage-5 addition, BYOK support) overrides litellm's default
    env-based key resolution for this call only. Pass ``model`` already
    provider-prefixed (e.g. ``"anthropic/claude-3-5-sonnet-latest"``,
    ``"openai/gpt-4o"``, ``"openrouter/mistralai/mistral-large"``) when using
    this — a model string containing ``"/"`` is treated as fully-qualified
    and is NOT re-prefixed with the Gemini ``gemini/``/``vertex_ai/`` prefix,
    and the Gemini-model fallback chain / vertex project+location kwargs are
    skipped, since those only make sense for Gemini calls. Omitting
    ``api_key`` (the default) preserves the exact previous behavior for
    every existing bare-model-name (Gemini) caller.
    """
    provider = _provider_prefix()
    already_qualified = "/" in model
    bare_model_requested = model.rsplit("/", 1)[-1] if already_qualified else model
    litellm_model = model if already_qualified else _litellm_model(model)
    fallbacks = (
        []
        if already_qualified
        else [_litellm_model(m) for m in _FALLBACK_MODELS if m != model]
    )

    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "messages": messages,
        "num_retries": max(max_attempts - 1, 0),
        "fallbacks": fallbacks,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if tools is not None:
        kwargs["tools"] = tools
    if response_format is not None:
        kwargs["response_format"] = response_format
    if api_key is not None:
        kwargs["api_key"] = api_key
    if provider == "vertex_ai" and not already_qualified:
        kwargs["vertex_project"] = GOOGLE_CLOUD_PROJECT
        kwargs["vertex_location"] = GOOGLE_CLOUD_LOCATION

    start = time.monotonic()
    status = "ok"
    error: Optional[str] = None
    response = None
    try:
        response = await litellm.acompletion(**kwargs)
    except Exception as exc:  # noqa: BLE001
        status = "error"
        error = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)
        await _write_ledger(
            user_id=user_id, turn_id=turn_id, message_id=message_id, feature=feature,
            provider=provider, model=bare_model_requested, is_fallback=False,
            prompt_tokens=0, completion_tokens=0, total_tokens=0, cost_usd=None,
            latency_ms=latency_ms, status=status, error=error,
        )
        raise
    latency_ms = int((time.monotonic() - start) * 1000)

    model_used = getattr(response, "model", None) or litellm_model
    # litellm prefixes the response model with the same provider/model string
    # we requested; strip it back down to the bare model id for storage/parity
    # with main.py's model names.
    bare_model_used = model_used.rsplit("/", 1)[-1]
    is_fallback = bare_model_used != bare_model_requested

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) or 0
    completion_tokens = getattr(usage, "completion_tokens", None) or 0
    total_tokens = getattr(usage, "total_tokens", None) or (prompt_tokens + completion_tokens)

    cost_usd: Optional[float] = None
    try:
        cost_usd = litellm.completion_cost(completion_response=response) or None
    except Exception:  # noqa: BLE001
        logger.warning("llm.complete: cost calculation failed for model %s", bare_model_used)

    text = ""
    function_calls: list = []
    try:
        choice = response.choices[0]
        text = (getattr(choice.message, "content", None) or "").strip()
        function_calls = getattr(choice.message, "tool_calls", None) or []
    except Exception:  # noqa: BLE001
        logger.warning("llm.complete: could not extract text/tool_calls from response")

    await _write_ledger(
        user_id=user_id, turn_id=turn_id, message_id=message_id, feature=feature,
        provider=provider, model=bare_model_used, is_fallback=is_fallback,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, cost_usd=cost_usd, latency_ms=latency_ms,
        status=status, error=error,
    )

    return LLMResult(
        text=text,
        function_calls=function_calls,
        raw_response=response,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        model_used=bare_model_used,
        is_fallback=is_fallback,
    )


async def embed(
    *,
    texts: list[str],
    model: str = EMBED_MODEL_DEFAULT,
    feature: str = "embedding",
    user_id: Optional[str] = None,
    max_attempts: int = 4,
    output_dimensionality: Optional[int] = None,
    task_type: Optional[str] = None,
) -> list[list[float]]:
    """Batch text embedding via ``litellm.aembedding``.

    Mirrors ``complete()``'s AI-Studio-vs-Vertex-AI billing-prefix selection
    (``_provider_prefix()`` / ``_litellm_model()``) and manual-retry-with-
    backoff shape, since litellm's embedding surface doesn't get the same
    ``fallbacks=``/model-routing treatment as chat completions here — there's
    no equivalent embed-model fallback chain in this codebase (unlike
    ``_FALLBACK_MODELS`` for ``complete()``/``stream()``).

    ``output_dimensionality`` and ``task_type`` are Gemini-embedding-specific
    optional parameters (matching ``google-genai``'s
    ``EmbedContentConfig.output_dimensionality`` and the legacy
    ``task_type`` param used by ``text-embedding-004``); litellm forwards
    them straight through to the provider. Omit both for models/providers
    that don't use them.

    Retries on transient errors (429/500/502/503/504, matching
    plugins/memory.py's previous ``_embed_with_retry`` behavior) with the
    same 1s/2s/4s/8s backoff. Returns one embedding vector per input text,
    in the same order as ``texts``.

    NOTE on cost tracking: ``litellm.completion_cost()`` is written for chat
    completions and does not reliably compute a cost for embedding responses
    across providers/versions — rather than guess at an API shape, this
    function skips cost calculation entirely and writes ``cost_usd=None`` to
    the ledger (token counts, when available from the response, are still
    recorded). Anyone who needs embedding cost tracking should verify
    litellm's current embedding-cost API with live credentials before
    relying on a number here.
    """
    provider = _provider_prefix()
    litellm_model = _litellm_model(model)

    kwargs: dict[str, Any] = {"model": litellm_model, "input": texts}
    if output_dimensionality is not None:
        kwargs["output_dimensionality"] = output_dimensionality
    if task_type is not None:
        kwargs["task_type"] = task_type
    if provider == "vertex_ai":
        kwargs["vertex_project"] = GOOGLE_CLOUD_PROJECT
        kwargs["vertex_location"] = GOOGLE_CLOUD_LOCATION

    start = time.monotonic()
    response = None
    last_error: Optional[str] = None

    for attempt in range(max_attempts):
        try:
            response = await litellm.aembedding(**kwargs)
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            status_code = getattr(exc, "status_code", None)
            transient = status_code in (429, 500, 502, 503, 504)
            last_error = str(exc)
            if not transient or attempt == max_attempts - 1:
                latency_ms = int((time.monotonic() - start) * 1000)
                await _write_ledger(
                    user_id=user_id, turn_id=None, message_id=None, feature=feature,
                    provider=provider, model=model, is_fallback=False,
                    prompt_tokens=0, completion_tokens=0, total_tokens=0, cost_usd=None,
                    latency_ms=latency_ms, status="error", error=last_error,
                )
                raise
            backoff = 2 ** attempt  # 1s, 2s, 4s, 8s
            logger.warning(
                "llm.embed: transient error (%s) on model %s — backing off %ds (attempt %d/%d)",
                status_code, model, backoff, attempt + 1, max_attempts,
            )
            await asyncio.sleep(backoff)

    latency_ms = int((time.monotonic() - start) * 1000)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) or 0
    total_tokens = getattr(usage, "total_tokens", None) or prompt_tokens

    vectors: list[list[float]] = []
    try:
        data = getattr(response, "data", None) or []
        for item in data:
            values = (
                item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
            )
            if values is None:
                raise RuntimeError("embedding value missing in response")
            vectors.append(list(values))
        if not vectors:
            raise RuntimeError("empty embeddings response")
    except Exception:
        logger.warning("llm.embed: could not extract embedding vectors from response")
        await _write_ledger(
            user_id=user_id, turn_id=None, message_id=None, feature=feature,
            provider=provider, model=model, is_fallback=False,
            prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=total_tokens,
            cost_usd=None, latency_ms=latency_ms, status="error",
            error="could not extract embedding vectors from response",
        )
        raise

    await _write_ledger(
        user_id=user_id, turn_id=None, message_id=None, feature=feature,
        provider=provider, model=model, is_fallback=False,
        prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=total_tokens,
        cost_usd=None, latency_ms=latency_ms, status="ok", error=None,
    )

    return vectors


async def _write_ledger(
    *,
    user_id: Optional[str],
    turn_id: Optional[str],
    message_id: Optional[str],
    feature: str,
    provider: str,
    model: str,
    is_fallback: bool,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: Optional[float],
    latency_ms: int,
    status: str,
    error: Optional[str],
) -> None:
    """Best-effort insert into llm_calls. Never raises — a ledger/logging
    hiccup must never break the caller's actual LLM result."""
    try:
        supabase.table("llm_calls").insert({
            "user_id": user_id,
            "turn_id": turn_id,
            "message_id": message_id,
            "feature": feature,
            "provider": provider,
            "model": model,
            "is_fallback": is_fallback,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "status": status,
            "error": error,
        }).execute()
    except Exception:  # noqa: BLE001
        logger.warning("llm.complete: failed to write llm_calls ledger row for feature=%s", feature)


# ---------------------------------------------------------------------------
# Stage 4: streaming + Gemini-native <-> litellm/OpenAI conversation-history
# conversion helpers.
# ---------------------------------------------------------------------------


class _StreamedToolCallFunction:
    """Mimics litellm's (OpenAI's) ``ChatCompletionMessageToolCall.function``
    shape (``.name``, ``.arguments`` as a JSON string) closely enough that
    ``parsed_tool_calls()`` can treat streamed and non-streamed results
    identically."""

    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _StreamedToolCall:
    """Mimics litellm's ``ChatCompletionMessageToolCall`` (``.id``, ``.type``,
    ``.function``), assembled by hand from streamed tool-call delta chunks
    since litellm/most providers only send the full tool_calls objects on
    the final non-streamed response."""

    def __init__(self, id: str, name: str, arguments: str):  # noqa: A002
        self.id = id
        self.type = "function"
        self.function = _StreamedToolCallFunction(name=name, arguments=arguments)


async def stream(
    *,
    model: str,
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    on_token=None,
    max_attempts: int = 4,
    feature: str,
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> LLMResult:
    """Streaming counterpart to ``complete()``.

    Mirrors ``complete()``'s billing-prefix selection, fallback chain, and
    cost/ledger tracking, but iterates ``litellm.acompletion(..., stream=True)``
    chunks, calling ``await on_token(text_delta)`` for each visible text
    delta (skipped when ``None``, so callers may pass a sync-looking no-op or
    omit it entirely). Tool-call deltas are accumulated across chunks into
    the same ``LLMResult.function_calls`` shape ``complete()`` returns
    (objects with ``.id``/``.function.name``/``.function.arguments``), so
    ``parsed_tool_calls()`` works identically on either function's result.

    Three-tier fallback, mirroring main.py's ``_gemini_stream``:
      1. Stream the primary model.
      2. On failure, stream each fallback model in turn.
      3. If every streaming attempt fails, fall back to non-streaming
         ``complete()`` as a last resort (and, if there was text, deliver it
         as a single synthetic ``on_token`` call so callers that render
         incrementally still get *something*).
    """
    provider = _provider_prefix()
    fallbacks = [_litellm_model(m) for m in _FALLBACK_MODELS if m != model]
    chain = [_litellm_model(model)] + fallbacks

    async def _run_stream(litellm_model: str) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "stream": True,
            # Ask providers that support it (OpenAI-compatible streaming) to
            # attach usage on the final chunk. Harmless no-op if unsupported.
            "stream_options": {"include_usage": True},
        }
        if tools is not None:
            kwargs["tools"] = tools
        if provider == "vertex_ai":
            kwargs["vertex_project"] = GOOGLE_CLOUD_PROJECT
            kwargs["vertex_location"] = GOOGLE_CLOUD_LOCATION

        start = time.monotonic()
        text_parts: list[str] = []
        tool_call_chunks: dict[int, dict[str, str]] = {}
        last_chunk = None

        response_stream = await litellm.acompletion(**kwargs)
        async for chunk in response_stream:
            last_chunk = chunk
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                text_parts.append(content)
                if on_token:
                    await on_token(content)
            delta_tool_calls = getattr(delta, "tool_calls", None)
            if delta_tool_calls:
                for tc_delta in delta_tool_calls:
                    idx = getattr(tc_delta, "index", 0) or 0
                    slot = tool_call_chunks.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if getattr(tc_delta, "id", None):
                        slot["id"] = tc_delta.id
                    fn = getattr(tc_delta, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments

        latency_ms = int((time.monotonic() - start) * 1000)

        function_calls = [
            _StreamedToolCall(
                id=slot["id"] or f"call_{idx}",
                name=slot["name"],
                arguments=slot["arguments"],
            )
            for idx, slot in sorted(tool_call_chunks.items())
        ]
        text = "".join(text_parts).strip()

        usage = getattr(last_chunk, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) or 0
        completion_tokens = getattr(usage, "completion_tokens", None) or 0
        total_tokens = getattr(usage, "total_tokens", None) or (prompt_tokens + completion_tokens)

        model_used = getattr(last_chunk, "model", None) or litellm_model
        bare_model_used = model_used.rsplit("/", 1)[-1]
        is_fallback = bare_model_used != model

        cost_usd: Optional[float] = None
        try:
            if last_chunk is not None:
                cost_usd = litellm.completion_cost(completion_response=last_chunk) or None
        except Exception:  # noqa: BLE001
            logger.warning("llm.stream: cost calculation failed for model %s", bare_model_used)

        await _write_ledger(
            user_id=user_id, turn_id=turn_id, message_id=message_id, feature=feature,
            provider=provider, model=bare_model_used, is_fallback=is_fallback,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total_tokens, cost_usd=cost_usd, latency_ms=latency_ms,
            status="ok", error=None,
        )

        return LLMResult(
            text=text,
            function_calls=function_calls,
            raw_response=last_chunk,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            model_used=bare_model_used,
            is_fallback=is_fallback,
        )

    last_exc: Optional[Exception] = None
    for litellm_model in chain:
        try:
            return await _run_stream(litellm_model)
        except Exception as exc:  # noqa: BLE001
            logger.exception("llm.stream: streaming failed on %s", litellm_model)
            last_exc = exc
            continue

    logger.warning(
        "llm.stream: every streaming attempt failed (%s); falling back to non-stream complete()",
        last_exc,
    )
    result = await complete(
        model=model, messages=messages, tools=tools, max_attempts=max_attempts,
        feature=feature, user_id=user_id, turn_id=turn_id, message_id=message_id,
    )
    if on_token and result.text and not result.function_calls:
        await on_token(result.text)
    return result


def to_litellm_messages(contents: list, system_instruction: Optional[str] = None) -> list[dict]:
    """Convert a Gemini-native multi-turn conversation into litellm's
    OpenAI-compatible ``messages`` list.

    ``contents`` is a list of Gemini-shaped "Content" objects — duck-typed,
    not isinstance-checked, so this accepts both real
    ``google.genai.types.Content`` instances (used for chat history built
    before the tool loop starts) and the lightweight
    ``app/core/gemini_compat.py`` stand-ins (used for turns the litellm path
    itself produces). Each Content needs ``.role`` ("user"/"model") and
    ``.parts``; each Part needs some subset of ``.text``,
    ``.function_call`` (``.name``/``.args``), ``.function_response``
    (``.name``/``.response``), ``.thought`` (skipped when truthy — thinking
    parts aren't replayed into history, matching how the Gemini-native loop
    doesn't try to distinguish them either).

    Produces:
      - plain ``{"role": "user"/"system", "content": str}`` for text turns.
      - ``{"role": "assistant", "content": ..., "tool_calls": [...]}`` for a
        model turn that called tool(s), matching litellm/OpenAI's
        ``tool_calls`` shape (``id``, ``type": "function"``,
        ``function.name``/``function.arguments`` as a JSON string).
      - ``{"role": "tool", "tool_call_id": ..., "content": ...}`` for each
        function-response part, matched by position to the ``tool_calls``
        ids emitted for the immediately preceding assistant turn (Gemini's
        function_response parts carry a tool *name*, not a call id, so the
        pairing has to be positional — this assumes each function-response
        Content immediately follows the assistant Content whose tool_calls
        it's answering, in the same order, which is how both main.py's loop
        and graph_agent.py construct ``contents``).

    NOTE: does not handle inline binary parts (``Part.from_bytes`` — used
    for voice-message audio input) or ``file_data`` parts. Those are
    silently dropped. Needs live verification before KIN_USE_LITELLM is
    trusted for audio-message turns.
    """
    messages: list[dict] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    pending_call_ids: list[str] = []
    call_counter = 0

    for content in contents:
        role = getattr(content, "role", None) or "user"
        parts = getattr(content, "parts", None) or []

        text_chunks: list[str] = []
        tool_calls: list[dict] = []
        function_responses: list[tuple[Optional[str], Any]] = []

        for part in parts:
            if getattr(part, "thought", False):
                continue
            fc = getattr(part, "function_call", None)
            fr = getattr(part, "function_response", None)
            text = getattr(part, "text", None)
            if fc is not None:
                call_counter += 1
                call_id = f"call_{call_counter}"
                raw_args = getattr(fc, "args", None) or {}
                args = raw_args if isinstance(raw_args, dict) else dict(raw_args)
                tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {"name": fc.name, "arguments": json.dumps(args, default=str)},
                })
            elif fr is not None:
                function_responses.append((getattr(fr, "name", None), getattr(fr, "response", None)))
            elif text:
                text_chunks.append(text)

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": ("\n".join(text_chunks) or None),
                "tool_calls": tool_calls,
            })
            pending_call_ids = [tc["id"] for tc in tool_calls]
            continue

        if function_responses:
            for i, (_name, response) in enumerate(function_responses):
                call_id = (
                    pending_call_ids[i] if i < len(pending_call_ids)
                    else f"call_unmatched_{call_counter}_{i}"
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(response, default=str),
                })
            pending_call_ids = []
            continue

        if text_chunks:
            messages.append({
                "role": "assistant" if role == "model" else "user",
                "content": "\n".join(text_chunks),
            })
            pending_call_ids = []

    return messages


def parsed_tool_calls(result: LLMResult) -> list[dict]:
    """Normalize ``LLMResult.function_calls`` (litellm's raw
    ``ChatCompletionMessageToolCall``-shaped objects, from either
    ``complete()`` or ``stream()``) into ``[{"id", "name", "args"}, ...]``,
    JSON-decoding each tool call's ``arguments`` string. Skips (and logs)
    any entry that fails to parse rather than raising — a single malformed
    tool call from the model shouldn't take down the whole turn."""
    out: list[dict] = []
    for tc in result.function_calls or []:
        try:
            fn = tc.function
            name = fn.name
            raw_args = fn.arguments or "{}"
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            if not isinstance(args, dict):
                args = {}
        except Exception:  # noqa: BLE001
            logger.warning("llm.parsed_tool_calls: failed to parse tool call %r", tc)
            continue
        out.append({"id": getattr(tc, "id", None), "name": name, "args": args})
    return out
