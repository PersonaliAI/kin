-- Security-audit remediation: OAuth-state JWTs minted by main.py's
-- _mint_state (Google/Microsoft/social/MCP OAuth "state" param) previously
-- had no single-use enforcement — a captured state token (e.g. leaked via a
-- Referer header on the provider's redirect) stayed valid for reuse until
-- its 10-minute exp. This table lets _decode_state/_decode_state_claim
-- reject a state JWT whose jti has already been consumed, or which was
-- never issued by this backend in the first place.
--
-- Pure internal table, written/read only by the backend's service-role
-- client — no user-facing access, same pattern as lemon_events
-- (20260511120000) and llm_calls (20260824000000).
CREATE TABLE IF NOT EXISTS oauth_state_nonces (
    jti TEXT PRIMARY KEY,
    -- NOT a FK to users(id): OAuth state carries the Supabase Auth user id
    -- (auth.users.id / users.auth_user_id), not the local users.id primary
    -- key, so it's stored unconstrained here rather than assuming a schema
    -- relationship that may not hold.
    auth_user_id UUID,
    consumed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oauth_state_nonces_expires ON oauth_state_nonces(expires_at);

ALTER TABLE oauth_state_nonces ENABLE ROW LEVEL SECURITY;
