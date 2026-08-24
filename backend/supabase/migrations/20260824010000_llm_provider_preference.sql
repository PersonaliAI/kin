-- Multi-provider model selector: lets a user route their chat turns to a
-- BYOK provider (openai/anthropic/openrouter) instead of the platform's
-- Gemini key. Mirrors the existing per-feature BYOK column pattern (see
-- 20260813010000_voice_agents_byok.sql) but as a preference on the user
-- row rather than per-agent, since web chat has exactly one active model
-- selection at a time. Actual encrypted keys still live in the existing
-- user_credentials table (integration_slug = 'llm:<provider>'), not here —
-- this migration only adds the *selection*, not the secret.

ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_provider TEXT NOT NULL DEFAULT 'gemini';
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_model TEXT;

-- No RLS changes needed — users already has its own RLS policies covering
-- these new columns via the existing row-level rules on the table.
