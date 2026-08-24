-- Per-post platform settings (Instagram post type, X reply privacy, LinkedIn
-- visibility, YouTube privacy, TikTok toggles, ...) captured by the composer
-- accordion but previously never persisted or sent to any provider.
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS settings JSONB;

-- Real outbound webhooks — fired by /cron/publish-social-posts whenever a
-- post's state changes to 'published' or 'failed', mirroring Postiz's
-- IntegrationsWebhooks feature (simplified: one webhook per user, not
-- scoped per-integration).
CREATE TABLE IF NOT EXISTS social_webhooks (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  url        TEXT NOT NULL,
  secret     TEXT,
  active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id)
);

DROP TRIGGER IF EXISTS social_webhooks_updated_at ON social_webhooks;
CREATE TRIGGER social_webhooks_updated_at BEFORE UPDATE ON social_webhooks
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- Analytics were previously only ever fetched once, at publish time —
-- schedule the refresh cron every 6 hours (same secret placeholder pattern
-- as 20260805000000_social_release_and_cron.sql).
SELECT cron.schedule(
  'social-refresh-analytics',
  '0 */6 * * *',
  $$
  SELECT net.http_post(
    url := 'https://personaliai-api-376030619262.us-central1.run.app/cron/refresh-social-analytics',
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := jsonb_build_object('secret', 'your_custom_secret_here')
  )
  $$
);
