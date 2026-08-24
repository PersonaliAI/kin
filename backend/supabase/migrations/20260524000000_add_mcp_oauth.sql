-- Migration to add OAuth 2.0 columns to mcp_servers table
ALTER TABLE mcp_servers 
ADD COLUMN IF NOT EXISTS oauth_flow_status TEXT DEFAULT 'none',
ADD COLUMN IF NOT EXISTS oauth_client_id TEXT,
ADD COLUMN IF NOT EXISTS oauth_client_secret TEXT,
ADD COLUMN IF NOT EXISTS oauth_auth_url TEXT,
ADD COLUMN IF NOT EXISTS oauth_token_url TEXT,
ADD COLUMN IF NOT EXISTS oauth_scopes TEXT,
ADD COLUMN IF NOT EXISTS oauth_access_token TEXT,
ADD COLUMN IF NOT EXISTS oauth_refresh_token TEXT,
ADD COLUMN IF NOT EXISTS oauth_token_expires_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS oauth_code_verifier TEXT;
