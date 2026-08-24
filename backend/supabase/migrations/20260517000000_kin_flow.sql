-- Kin Flow — chat-built workflow automation
--
-- Adds the database layer for the new product:
--   • flows                     — user-owned workflow definitions (DSL in JSONB)
--   • flow_triggers             — cron/webhook/email/manual trigger registrations
--   • flow_runs                 — one row per execution
--   • flow_steps                — one row per step execution (durability spine)
--   • integrations              — built-in + community-published integrations
--   • integration_reviews       — marketplace ratings
--   • user_credentials          — encrypted API keys / OAuth tokens per integration
--   • integration_installs      — which integrations a user has installed (UX state)

-- ------------------------------------------------------------------
-- Workflows
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS flows (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  description     TEXT,
  dsl             JSONB NOT NULL DEFAULT '{}'::jsonb,
  status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','active','paused','archived')),
  -- For UX: track which connections this flow still needs the user to set up
  missing_credentials JSONB NOT NULL DEFAULT '[]'::jsonb,
  last_run_at     TIMESTAMPTZ,
  last_run_status TEXT,
  total_runs      INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flows_user ON flows(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_flows_status ON flows(status) WHERE status = 'active';

-- ------------------------------------------------------------------
-- Trigger registrations
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS flow_triggers (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flow_id               UUID NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
  type                  TEXT NOT NULL
                          CHECK (type IN ('cron','webhook','manual','email','form','chat')),
  config                JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- For webhook triggers: secret + auto-generated URL
  webhook_secret        TEXT,
  -- For cron triggers: GCP Cloud Scheduler job name (so we can delete on un-deploy)
  cloud_scheduler_id    TEXT,
  enabled               BOOLEAN NOT NULL DEFAULT TRUE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flow_triggers_flow ON flow_triggers(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_triggers_webhook ON flow_triggers(webhook_secret)
  WHERE webhook_secret IS NOT NULL;

-- ------------------------------------------------------------------
-- Runs (one row per execution)
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS flow_runs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flow_id           UUID NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  triggered_by      TEXT NOT NULL
                      CHECK (triggered_by IN ('cron','webhook','manual','chat','email','form','retry')),
  trigger_payload   JSONB,
  status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','running','succeeded','failed','dead','cancelled')),
  current_node_id   TEXT,
  cost_cents        INT NOT NULL DEFAULT 0,
  started_at        TIMESTAMPTZ,
  finished_at       TIMESTAMPTZ,
  error_summary     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flow_runs_flow ON flow_runs(flow_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flow_runs_user ON flow_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flow_runs_status ON flow_runs(status)
  WHERE status IN ('queued','running');

-- ------------------------------------------------------------------
-- Steps (durability spine — every step writes its result here BEFORE
-- the next step is enqueued, so a worker crash never silently drops data)
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS flow_steps (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id            UUID NOT NULL REFERENCES flow_runs(id) ON DELETE CASCADE,
  node_id           TEXT NOT NULL,
  integration_slug  TEXT,
  action            TEXT,
  attempt           INT NOT NULL DEFAULT 1,
  idempotency_key   TEXT NOT NULL UNIQUE,
  input             JSONB,
  output            JSONB,
  error             TEXT,
  status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','running','succeeded','failed','skipped')),
  started_at        TIMESTAMPTZ,
  finished_at       TIMESTAMPTZ,
  duration_ms       INT,
  cost_cents        INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_flow_steps_run ON flow_steps(run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_flow_steps_status ON flow_steps(status)
  WHERE status IN ('queued','running');

-- ------------------------------------------------------------------
-- Integration catalog (built-in + community-published)
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS integrations (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                 TEXT UNIQUE NOT NULL,
  name                 TEXT NOT NULL,
  description          TEXT,
  category             TEXT,                         -- communication / productivity / data / ai / storage / trigger
  icon_url             TEXT,
  publisher_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
  publisher_name       TEXT,                         -- denormalized for display
  -- The full integration manifest:
  --   { auth: {...}, actions: [{name, inputs, outputs, request}], triggers: [...] }
  manifest             JSONB NOT NULL DEFAULT '{}'::jsonb,
  source               TEXT NOT NULL DEFAULT 'community'
                          CHECK (source IN ('builtin','community','verified')),
  status               TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','published','flagged','removed')),
  install_count        INT NOT NULL DEFAULT 0,
  rating_sum           INT NOT NULL DEFAULT 0,
  rating_count         INT NOT NULL DEFAULT 0,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_integrations_category
  ON integrations(category, status)
  WHERE status = 'published';
CREATE INDEX IF NOT EXISTS idx_integrations_publisher ON integrations(publisher_user_id);

-- ------------------------------------------------------------------
-- User-installed integrations (so we can show "your installed apps")
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS integration_installs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  integration_slug  TEXT NOT NULL REFERENCES integrations(slug) ON DELETE CASCADE,
  installed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, integration_slug)
);

CREATE INDEX IF NOT EXISTS idx_installs_user ON integration_installs(user_id);

-- ------------------------------------------------------------------
-- User credentials (KMS-encrypted at the app layer; we only store ciphertext here)
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_credentials (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  integration_slug  TEXT NOT NULL,
  auth_type         TEXT NOT NULL CHECK (auth_type IN ('oauth','api_key','none')),
  -- AES-256-GCM encrypted JSON. App layer encrypts/decrypts; DB never sees plaintext.
  encrypted_payload BYTEA NOT NULL,
  expires_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, integration_slug)
);

CREATE INDEX IF NOT EXISTS idx_credentials_user ON user_credentials(user_id);

-- ------------------------------------------------------------------
-- Marketplace reviews
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS integration_reviews (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  integration_id  UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating          INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(integration_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_integration
  ON integration_reviews(integration_id, created_at DESC);

-- ------------------------------------------------------------------
-- updated_at triggers
-- ------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_flows_updated_at ON flows;
CREATE TRIGGER trg_flows_updated_at
  BEFORE UPDATE ON flows FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_integrations_updated_at ON integrations;
CREATE TRIGGER trg_integrations_updated_at
  BEFORE UPDATE ON integrations FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_credentials_updated_at ON user_credentials;
CREATE TRIGGER trg_credentials_updated_at
  BEFORE UPDATE ON user_credentials FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

-- ------------------------------------------------------------------
-- Row Level Security — users see only their own rows; backend uses
-- service role and bypasses these.
-- ------------------------------------------------------------------

ALTER TABLE flows ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

-- Flows: owner-only
DROP POLICY IF EXISTS "flows_own_select" ON flows;
CREATE POLICY "flows_own_select" ON flows FOR SELECT
  USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "flows_own_modify" ON flows;
CREATE POLICY "flows_own_modify" ON flows FOR ALL
  USING (user_id = public.current_user_id());

-- Flow triggers: derive ownership via flow
DROP POLICY IF EXISTS "flow_triggers_via_flow" ON flow_triggers;
CREATE POLICY "flow_triggers_via_flow" ON flow_triggers FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM flows f
      WHERE f.id = flow_triggers.flow_id AND f.user_id = public.current_user_id()
    )
  );

-- Runs + steps: owner-only
DROP POLICY IF EXISTS "flow_runs_own" ON flow_runs;
CREATE POLICY "flow_runs_own" ON flow_runs FOR SELECT
  USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "flow_steps_via_run" ON flow_steps;
CREATE POLICY "flow_steps_via_run" ON flow_steps FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM flow_runs r
      WHERE r.id = flow_steps.run_id AND r.user_id = public.current_user_id()
    )
  );

-- Installed apps + credentials: owner-only
DROP POLICY IF EXISTS "installs_own" ON integration_installs;
CREATE POLICY "installs_own" ON integration_installs FOR ALL
  USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "credentials_own_select" ON user_credentials;
CREATE POLICY "credentials_own_select" ON user_credentials FOR SELECT
  USING (user_id = public.current_user_id());
-- Note: encrypted_payload is fine to expose to the owner (still ciphertext).
-- Backend service role handles decryption.

DROP POLICY IF EXISTS "credentials_own_delete" ON user_credentials;
CREATE POLICY "credentials_own_delete" ON user_credentials FOR DELETE
  USING (user_id = public.current_user_id());

-- Integrations: published rows visible to everyone, draft visible to publisher
DROP POLICY IF EXISTS "integrations_public_read" ON integrations;
CREATE POLICY "integrations_public_read" ON integrations FOR SELECT
  USING (status = 'published' OR publisher_user_id = public.current_user_id());

DROP POLICY IF EXISTS "integrations_own_modify" ON integrations;
CREATE POLICY "integrations_own_modify" ON integrations FOR ALL
  USING (publisher_user_id = public.current_user_id());

-- Reviews: anyone can read, only author can mutate
DROP POLICY IF EXISTS "reviews_public_read" ON integration_reviews;
CREATE POLICY "reviews_public_read" ON integration_reviews FOR SELECT
  USING (TRUE);

DROP POLICY IF EXISTS "reviews_own_modify" ON integration_reviews;
CREATE POLICY "reviews_own_modify" ON integration_reviews FOR ALL
  USING (user_id = public.current_user_id());

-- ------------------------------------------------------------------
-- Helper: compute average rating
-- ------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.integration_average_rating(integration_uuid uuid)
RETURNS NUMERIC
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(AVG(rating)::NUMERIC(3,2), 0)
  FROM integration_reviews
  WHERE integration_id = integration_uuid;
$$;
