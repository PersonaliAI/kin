-- Migration: 12 tables were exposed to PostgREST with no Row Level Security
-- (Supabase Security Advisor). All were added after the original RLS setup
-- in 20260511000000_auth_link_and_rls.sql and never covered. Backend writes
-- go through the service role (bypasses RLS) — these policies exist for
-- owner-scoped dashboard/direct-client access, using the same
-- public.current_user_id() helper (maps auth.uid() -> users.id) as every
-- other kin table.

-- ── Direct user_id ownership ─────────────────────────────────────────────
ALTER TABLE chat_history_summaries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their chat history summaries" ON chat_history_summaries
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

-- mcp_servers holds OAuth client secrets/tokens — owner-only, no exceptions.
ALTER TABLE mcp_servers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their MCP servers" ON mcp_servers
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

ALTER TABLE scheduled_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their scheduled tasks" ON scheduled_tasks
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

ALTER TABLE social_analytics_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners view their daily social analytics" ON social_analytics_daily
  FOR SELECT TO authenticated
  USING (user_id = public.current_user_id());

ALTER TABLE social_auto_posts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their auto-post rules" ON social_auto_posts
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

ALTER TABLE social_posts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their social posts" ON social_posts
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

ALTER TABLE social_tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their social tags" ON social_tags
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

-- social_webhooks holds a signing secret — owner-only.
ALTER TABLE social_webhooks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage their social webhooks" ON social_webhooks
  FOR ALL TO authenticated
  USING (user_id = public.current_user_id())
  WITH CHECK (user_id = public.current_user_id());

-- ── Ownership via a join (no user_id column of their own) ───────────────
ALTER TABLE social_analytics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners view analytics for their own posts" ON social_analytics
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM social_posts
      WHERE social_posts.id = social_analytics.post_id
        AND social_posts.user_id = public.current_user_id()
    )
  );

ALTER TABLE social_post_tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owners manage tags on their own posts" ON social_post_tags
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM social_posts
      WHERE social_posts.id = social_post_tags.post_id
        AND social_posts.user_id = public.current_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM social_posts
      WHERE social_posts.id = social_post_tags.post_id
        AND social_posts.user_id = public.current_user_id()
    )
  );

-- ── Pure internal tables — no user-facing access at all ─────────────────
ALTER TABLE lemon_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE _manual_migrations_log ENABLE ROW LEVEL SECURITY;
