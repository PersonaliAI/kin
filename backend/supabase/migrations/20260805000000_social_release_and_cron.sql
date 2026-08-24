-- Track the platform-side post id/url once a social_posts row is actually
-- published, so thread replies can comment on the right post and the UI can
-- link out to the live post (previously nothing captured this).
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS release_id TEXT;
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS release_url TEXT;

-- Schedule the two social-scheduling cron endpoints (added in
-- 20260802000000_postiz_social_scheduling.sql but never wired to a
-- scheduler — same pattern as morning-briefing-daily in setup_cron.sql).
-- Replace [CLOUD_RUN_URL] / the secret placeholder before running.

SELECT cron.schedule(
  'social-publish-posts',
  '* * * * *',
  $$
  SELECT net.http_post(
    url := 'https://personaliai-api-376030619262.us-central1.run.app/cron/publish-social-posts',
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := jsonb_build_object('secret', 'your_custom_secret_here')
  )
  $$
);

SELECT cron.schedule(
  'social-execute-autoposts',
  '*/10 * * * *',
  $$
  SELECT net.http_post(
    url := 'https://personaliai-api-376030619262.us-central1.run.app/cron/execute-autoposts',
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := jsonb_build_object('secret', 'your_custom_secret_here')
  )
  $$
);
