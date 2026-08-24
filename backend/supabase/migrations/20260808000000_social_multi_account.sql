-- Support multiple connected accounts per social platform (e.g. two X
-- accounts). The generic user_credentials table (shared with the unrelated
-- BYOK/integrations-marketplace system) enforces UNIQUE(user_id,
-- integration_slug), which is exactly the constraint that blocked this, so
-- social platform credentials get their own dedicated table instead.

CREATE TABLE IF NOT EXISTS social_accounts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug              TEXT NOT NULL,
  auth_type         TEXT NOT NULL CHECK (auth_type IN ('oauth', 'api_key', 'none')),
  encrypted_payload BYTEA NOT NULL,
  expires_at        TIMESTAMPTZ,
  display_name      TEXT,
  handle            TEXT,
  avatar_url        TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_accounts_user ON social_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_social_accounts_user_slug ON social_accounts(user_id, slug);

DROP TRIGGER IF EXISTS trg_social_accounts_updated_at ON social_accounts;
CREATE TRIGGER trg_social_accounts_updated_at
  BEFORE UPDATE ON social_accounts FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE social_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "social_accounts_own_select" ON social_accounts;
CREATE POLICY "social_accounts_own_select" ON social_accounts FOR SELECT
  USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "social_accounts_own_delete" ON social_accounts;
CREATE POLICY "social_accounts_own_delete" ON social_accounts FOR DELETE
  USING (user_id = public.current_user_id());

-- Link a post to the specific connected account it was scheduled against
-- (nullable + ON DELETE SET NULL: losing the account shouldn't delete post
-- history, integration_slug still carries the platform for display).
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS social_account_id UUID REFERENCES social_accounts(id) ON DELETE SET NULL;

-- Shares one id across the sibling rows created from a single multi-account
-- composer submit, so the UI can recognize them as "one post, N channels"
-- later without needing a join table.
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS group_id UUID;

CREATE INDEX IF NOT EXISTS idx_social_posts_account ON social_posts(social_account_id);
CREATE INDEX IF NOT EXISTS idx_social_posts_group ON social_posts(group_id);
