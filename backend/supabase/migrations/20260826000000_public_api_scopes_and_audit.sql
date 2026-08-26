-- Security-audit remediation: app/core/security.py's check_scope,
-- check_ip_allowlist, and log_api_access were written against a
-- chatty_api_keys/chatty_api_audit_log schema that was never actually
-- created in this database (that product line's tables don't exist here —
-- only the Kin-scoped kin_api_keys table from 20260720030000 does, and it
-- has no scopes/allowed_ips columns). That meant the three functions were
-- dead code and the "scopes enforced" / "IP allowlist" claims in the public
-- API's OpenAPI description (app/core/app_factory.py) were not actually
-- true for the one real public-API key table this app has.
--
-- This migration adds the missing columns to kin_api_keys and creates a
-- Kin-scoped audit log table (kin_api_audit_log, replacing the never-built
-- chatty_api_audit_log) so those checks can be wired in for real against
-- /api/v1/* traffic. See app/core/security.py and app/routers/chat.py.

ALTER TABLE kin_api_keys ADD COLUMN IF NOT EXISTS scopes TEXT[] NOT NULL DEFAULT ARRAY['chat', 'read'];
ALTER TABLE kin_api_keys ADD COLUMN IF NOT EXISTS allowed_ips TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS kin_api_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id UUID REFERENCES kin_api_keys(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    client_ip TEXT,
    request_id TEXT,
    status_code INT NOT NULL DEFAULT 200,
    duration_ms INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_kin_api_audit_log_user_created ON kin_api_audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_kin_api_audit_log_key_created ON kin_api_audit_log(key_id, created_at);

-- Written only by the backend's service-role client (fire-and-forget from
-- log_api_access); owners can read their own rows, same pattern as
-- kin_webhook_deliveries.
ALTER TABLE kin_api_audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Owners view their own API audit log" ON kin_api_audit_log;
CREATE POLICY "Owners view their own API audit log" ON kin_api_audit_log
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());
