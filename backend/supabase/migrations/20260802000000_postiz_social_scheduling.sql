-- Migration to add Postiz-equivalent social scheduling tables to Kin

-- 1. Create social_posts table
CREATE TABLE IF NOT EXISTS social_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  integration_slug TEXT NOT NULL, -- e.g. 'twitter', 'linkedin'
  state TEXT NOT NULL CHECK (state IN ('draft', 'queue', 'published', 'failed')) DEFAULT 'queue',
  publish_date TIMESTAMPTZ NOT NULL,
  content TEXT NOT NULL,
  image_url TEXT,
  parent_post_id UUID REFERENCES social_posts(id) ON DELETE CASCADE,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create social_auto_posts table (RSS / URL parsing and posting)
CREATE TABLE IF NOT EXISTS social_auto_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  generate_content BOOLEAN NOT NULL DEFAULT FALSE,
  integrations JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of integration slugs
  last_processed_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create social_tags table
CREATE TABLE IF NOT EXISTS social_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#6366f1',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_user_tag UNIQUE (user_id, name)
);

-- 4. Create social_post_tags association table
CREATE TABLE IF NOT EXISTS social_post_tags (
  post_id UUID REFERENCES social_posts(id) ON DELETE CASCADE NOT NULL,
  tag_id UUID REFERENCES social_tags(id) ON DELETE CASCADE NOT NULL,
  PRIMARY KEY (post_id, tag_id)
);

-- 5. Create social_analytics table for post stats
CREATE TABLE IF NOT EXISTS social_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id UUID REFERENCES social_posts(id) ON DELETE CASCADE UNIQUE NOT NULL,
  impressions INT DEFAULT 0,
  likes INT DEFAULT 0,
  reposts INT DEFAULT 0,
  comments INT DEFAULT 0,
  clicks INT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_social_posts_user ON social_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_social_posts_date_state ON social_posts(publish_date, state);
CREATE INDEX IF NOT EXISTS idx_social_auto_posts_user ON social_auto_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_social_tags_user ON social_tags(user_id);
CREATE INDEX IF NOT EXISTS idx_social_analytics_post ON social_analytics(post_id);

-- Trigger for updated_at tracking
DROP TRIGGER IF EXISTS social_posts_updated_at ON social_posts;
CREATE TRIGGER social_posts_updated_at BEFORE UPDATE ON social_posts
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

DROP TRIGGER IF EXISTS social_auto_posts_updated_at ON social_auto_posts;
CREATE TRIGGER social_auto_posts_updated_at BEFORE UPDATE ON social_auto_posts
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
