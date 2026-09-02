-- Signatures: reusable text snippets a user can insert into the composer,
-- optionally auto-filled into new posts (Postiz's Signatures.autoAdd).
CREATE TABLE IF NOT EXISTS social_signatures (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  content    TEXT NOT NULL,
  auto_add   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_social_signatures_user ON social_signatures(user_id);

-- Sets: reusable post templates (content + media) the composer can save to
-- and load from (Postiz's Sets).
CREATE TABLE IF NOT EXISTS social_sets (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  name       TEXT NOT NULL,
  content    TEXT NOT NULL,
  image_url  TEXT,
  media_type TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_social_sets_user ON social_sets(user_id);

-- Shortlinks: Kin's own redirect-and-count link shortener, used by the
-- composer's "Shorten links" action (Postiz's Organization.shortlink
-- preference, simplified to a per-post opt-in rather than an org default).
-- /l/{code} (public.controller-equivalent, see main.py) 302s to target_url
-- and increments clicks.
CREATE TABLE IF NOT EXISTS social_shortlinks (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  code       TEXT UNIQUE NOT NULL,
  target_url TEXT NOT NULL,
  clicks     INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_social_shortlinks_user ON social_shortlinks(user_id);
