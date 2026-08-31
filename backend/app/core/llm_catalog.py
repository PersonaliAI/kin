"""Static catalog of chat model providers/models for the frontend's model
selector, plus the small set of provider-id constants shared between
app/routers/settings.py (validating `preferred_provider`),
app/routers/llm_keys.py (BYOK key CRUD + the /api/llm-models catalog
endpoint), and app/routers/chat.py (BYOK chat routing).

Kept separate from plugins/llm_providers.py's DEFAULT_MODELS (which stays
untouched per the migration's constraints) — this is a superset used for
catalog/display purposes, not just default-model resolution.
"""
from __future__ import annotations

# Every provider a user can select as `preferred_provider`, including the
# platform-provided default.
ALL_PROVIDERS: set[str] = {"gemini", "openai", "anthropic", "openrouter", "xai"}

# Providers that require the user to bring their own API key.
BYOK_PROVIDERS: set[str] = {"openai", "anthropic", "openrouter", "xai"}

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.7-flash",
    "openai": "gpt-5.6-sol",
    "anthropic": "claude-fable-5",
    "openrouter": "mistralai/mistral-large",
    "xai": "grok-4.6",
}

# Static model catalog for GET /api/llm-models. `has_key`/`byok_required`
# are computed per-request by the router, not stored here.
MODEL_CATALOG: list[dict] = [
    {
        "id": "gemini",
        "label": "Gemini",
        "byok_required": False,
        "models": [
            {"id": "gemini-3.7-flash", "label": "Gemini 3.7 Flash (default)"},
            {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash"},
            {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
            {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite"},
            {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite"},
        ],
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "byok_required": True,
        "models": [
            {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
            {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
            {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
            {"id": "gpt-5.5", "label": "GPT-5.5"},
            {"id": "gpt-5.5-pro", "label": "GPT-5.5 Pro"},
        ],
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "byok_required": True,
        "models": [
            {"id": "claude-fable-5", "label": "Claude Fable 5"},
            {"id": "claude-opus-5", "label": "Claude Opus 5"},
            {"id": "claude-sonnet-5", "label": "Claude Sonnet 5"},
            {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5"},
            {"id": "claude-opus-4-8", "label": "Claude Opus 4.8"},
        ],
    },
    {
        "id": "xai",
        "label": "xAI",
        "byok_required": True,
        "models": [
            {"id": "grok-4.6", "label": "Grok 4.6"},
            {"id": "grok-4.5", "label": "Grok 4.5"},
            {"id": "grok-4", "label": "Grok 4"},
            {"id": "grok-4-heavy", "label": "Grok 4 Heavy"},
            {"id": "grok-3", "label": "Grok 3"},
        ],
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "byok_required": True,
        "models": [
            {"id": "mistralai/mistral-large", "label": "Mistral Large"},
            {"id": "meta-llama/llama-3.1-70b-instruct", "label": "Llama 3.1 70B"},
        ],
    },
]
