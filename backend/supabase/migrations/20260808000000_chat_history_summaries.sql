-- Rolling summary of conversation history older than the raw context window
-- (_load_history's `limit`, currently 20 messages) — without this, anything
-- before the last 20 messages silently disappeared from what the model can
-- see, which is why long conversations "lost" earlier context.
CREATE TABLE IF NOT EXISTS chat_history_summaries (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  source             TEXT NOT NULL,
  session_id         TEXT NOT NULL DEFAULT '',
  summary            TEXT NOT NULL DEFAULT '',
  summarized_through TIMESTAMPTZ,
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, source, session_id)
);
