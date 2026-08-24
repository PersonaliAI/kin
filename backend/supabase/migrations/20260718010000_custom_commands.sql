-- User-defined prompt shortcuts beyond the built-in /schedule command —
-- e.g. "/standup" -> "Summarize what's on my calendar and tasks for today
-- in 3 bullet points." Typing the shortcut runs the saved prompt.
CREATE TABLE IF NOT EXISTS custom_commands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,           -- without the leading slash, e.g. "standup"
  prompt_template TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_custom_commands_user ON custom_commands(user_id);

ALTER TABLE custom_commands ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "custom_commands_select_own" ON custom_commands;
CREATE POLICY "custom_commands_select_own" ON custom_commands
  FOR SELECT USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "custom_commands_delete_own" ON custom_commands;
CREATE POLICY "custom_commands_delete_own" ON custom_commands
  FOR DELETE USING (user_id = public.current_user_id());
