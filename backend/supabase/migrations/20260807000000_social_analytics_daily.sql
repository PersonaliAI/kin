-- Daily analytics rollup per post, so the dashboard trend chart can show
-- real history instead of a static placeholder shape. Written both at
-- publish time and by the existing 6-hourly /cron/refresh-social-analytics
-- (upserted per post per UTC day — a post can get multiple updates in the
-- same day, only the latest counts for that day).
CREATE TABLE IF NOT EXISTS social_analytics_daily (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id     UUID REFERENCES social_posts(id) ON DELETE CASCADE NOT NULL,
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  day         DATE NOT NULL,
  impressions INT DEFAULT 0,
  likes       INT DEFAULT 0,
  reposts     INT DEFAULT 0,
  comments    INT DEFAULT 0,
  clicks      INT DEFAULT 0,
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (post_id, day)
);

CREATE INDEX IF NOT EXISTS idx_social_analytics_daily_user_day ON social_analytics_daily(user_id, day);
