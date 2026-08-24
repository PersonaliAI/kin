-- Migration: llm_calls — usage/cost ledger for the new unified LLM-calling
-- module (app/core/llm.py, litellm-based). Every call through llm.complete()
-- writes one row here (success or final failure) alongside the existing
-- per-message token_count on the messages table — this ledger is additive,
-- not a replacement, and is the foundation for future cost dashboards /
-- per-feature spend tracking as more call sites migrate off _gemini_generate.
CREATE TABLE IF NOT EXISTS llm_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  turn_id TEXT,
  message_id TEXT,
  feature TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
  prompt_tokens INT NOT NULL DEFAULT 0,
  completion_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  cost_usd DOUBLE PRECISION,
  latency_ms INT,
  status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_user_created ON llm_calls(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_feature_created ON llm_calls(feature, created_at);

-- Pure internal table — written only by the backend's service-role client,
-- no user-facing access (matches the pattern for internal-only tables in
-- 20260818020000_rls_lockdown.sql, e.g. lemon_events).
ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;
