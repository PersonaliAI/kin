-- Proactive OAuth token refresh, independent of the publish sweep. The
-- publish cron only refreshes a token when a post is actually due for that
-- account, so an account with nothing currently scheduled — or whose token
-- expires between publish ticks — never gets refreshed ahead of time and
-- just fails the next time it's needed. Runs every 15 minutes, refreshing
-- any account whose token expires within the next 20 minutes.
SELECT cron.schedule(
  'social-refresh-tokens',
  '*/15 * * * *',
  $$
  SELECT net.http_post(
    url := 'https://personaliai-api-376030619262.us-central1.run.app/cron/refresh-social-tokens',
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := jsonb_build_object('secret', 'your_custom_secret_here')
  )
  $$
);
