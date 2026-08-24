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
ALL_PROVIDERS: set[str] = {"gemini", "openai", "anthropic", "openrouter"}

# Providers that require the user to bring their own API key.
BYOK_PROVIDERS: set[str] = {"openai", "anthropic", "openrouter"}

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-latest",
    "openrouter": "mistralai/mistral-large",
}

# Static model catalog for GET /api/llm-models. `has_key`/`byok_required`
# are computed per-request by the router, not stored here.
MODEL_CATALOG: list[dict] = [
    {
        "id": "gemini",
        "label": "Gemini",
        "byok_required": False,
        "models": [
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash (default)"},
            {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite"},
        ],
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "byok_required": True,
        "models": [
            {"id": "gpt-4o", "label": "GPT-4o"},
            {"id": "gpt-4o-mini", "label": "GPT-4o mini"},
        ],
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "byok_required": True,
        "models": [
            {"id": "claude-3-5-sonnet-latest", "label": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-latest", "label": "Claude 3.5 Haiku"},
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
