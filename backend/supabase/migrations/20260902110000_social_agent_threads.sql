-- Social Copilot agent threads — replaces the old one-shot "generate a
-- draft" form with a real multi-turn, tool-calling chat (schedule/draft
-- posts, look up connected accounts and recent posts, suggest best times —
-- see kin-backend/app/routers/social.py's SOCIAL_AGENT_TOOLS).
--
-- `messages` is the raw OpenAI-shaped conversation (user/assistant/tool
-- turns) sent back to the model on each new message — the authoritative
-- context. `display_log` is a separate, UI-facing trace (user/assistant
-- text plus a plain-language "action" entry per tool call, e.g. "Scheduled
-- a post to X for tomorrow 9am") so the frontend never has to parse raw
-- tool-call JSON to render the conversation.
CREATE TABLE IF NOT EXISTS social_agent_threads (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  title        TEXT,
  messages     JSONB NOT NULL DEFAULT '[]'::jsonb,
  display_log  JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_social_agent_threads_user ON social_agent_threads(user_id);

DROP TRIGGER IF EXISTS social_agent_threads_updated_at ON social_agent_threads;
CREATE TRIGGER social_agent_threads_updated_at BEFORE UPDATE ON social_agent_threads
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
