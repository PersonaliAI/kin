"""BYOK (bring your own key) support for non-Gemini AI Models.

Agentic tool-calling (lead capture, calendar booking, Gmail, memory) stays
Gemini-only — these providers' tool/function-call schemas differ enough that
wiring them in is a separate, larger effort. BYOK replies here are still
knowledge-base-grounded: the caller passes the same RAG-augmented system
prompt used for Gemini, just without function declarations.
"""
import os
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core import llm as core_llm

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-latest",
    "openrouter": "mistralai/mistral-large",
}


def _fernet() -> Fernet:
    key = os.environ.get("BYOK_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("BYOK_ENCRYPTION_KEY not configured")
    return Fernet(key.encode())


def encrypt_api_key(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_api_key(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Stored BYOK key could not be decrypted (wrong/rotated BYOK_ENCRYPTION_KEY?)") from exc


_PROVIDER_PREFIXES = {
    "anthropic": "anthropic",
    "openai": "openai",
    "openrouter": "openrouter",
}


async def generate_simple_reply(
    *,
    provider: str,
    api_key: str,
    model: Optional[str],
    system_prompt: str,
    history: list[dict[str, Any]],
    user_text: str,
    user_id: Optional[str] = None,
) -> str:
    """Plain text-completion reply (no function calling) via a customer-supplied key.

    Routed through ``app.core.llm.complete()`` (litellm) rather than raw
    provider SDKs. litellm normalizes the system prompt into each provider's
    native shape internally (Anthropic's separate ``system=`` param vs.
    OpenAI/OpenRouter's first ``{"role": "system", ...}`` message) from the
    same ``{"role": "system", ...}`` message this function builds for every
    provider — so, unlike the pre-migration code (which passed
    ``system=system_prompt`` directly to the Anthropic SDK and only
    prepended a system message for the OpenAI/OpenRouter branch), a single
    message-building path now covers all three providers.

    ``user_id`` is optional and threads through to complete()'s ledger
    (``llm_calls``) for cost/usage attribution; omit it if the caller
    doesn't have one available. As of this migration, this function has no
    call sites anywhere else in the repo (confirmed by grep) — it remains
    dead code, wired up to nothing.
    """
    prefix = _PROVIDER_PREFIXES.get(provider)
    if prefix is None:
        raise ValueError(f"Unknown BYOK provider: {provider}")

    model = model or DEFAULT_MODELS.get(provider, "")
    if not model:
        raise ValueError(f"Unknown BYOK provider: {provider}")

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages += [
        {"role": "user" if h.get("role") == "user" else "assistant", "content": h["content"]}
        for h in history if (h.get("content") or "").strip()
    ]
    messages.append({"role": "user", "content": user_text})

    kwargs: dict[str, Any] = dict(
        model=f"{prefix}/{model}",
        messages=messages,
        max_tokens=2048,
        api_key=api_key,
        feature="byok_chat",
        user_id=user_id,
    )
    # Matches the pre-migration behavior: temperature was only set on the
    # openai/openrouter branch, never on the anthropic branch.
    if provider in ("openai", "openrouter"):
        kwargs["temperature"] = 0.2

    result = await core_llm.complete(**kwargs)
    return result.text
