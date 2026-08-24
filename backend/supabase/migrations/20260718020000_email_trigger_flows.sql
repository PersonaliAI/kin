-- Event-driven triggers ("notify me when I get an email from X" / "...
-- containing keyword Y") — as opposed to scheduled_tasks, which only fire
-- on a cron schedule. Polled by /admin/run-email-trigger-flows, called
-- every minute by the pre-existing "kin-flow-email" Cloud Scheduler job
-- (which has been hitting this exact path since 2026-05-17 with nothing
-- behind it — this migration + the endpoint finally implement it).
CREATE TABLE IF NOT EXISTS email_trigger_flows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('gmail', 'outlook')),
  sender_filter TEXT,           -- e.g. "boss@company.com" — Gmail/Graph from: match
  keyword_filter TEXT,          -- e.g. "invoice" — matched in subject/body search
  prompt TEXT NOT NULL,         -- what Kin should do when a match fires
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'web', 'email')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (sender_filter IS NOT NULL OR keyword_filter IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_email_trigger_flows_active
  ON email_trigger_flows(is_active) WHERE is_active = TRUE;

ALTER TABLE email_trigger_flows ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "email_trigger_flows_select_own" ON email_trigger_flows;
CREATE POLICY "email_trigger_flows_select_own" ON email_trigger_flows
  FOR SELECT USING (user_id = public.current_user_id());

DROP POLICY IF EXISTS "email_trigger_flows_delete_own" ON email_trigger_flows;
CREATE POLICY "email_trigger_flows_delete_own" ON email_trigger_flows
  FOR DELETE USING (user_id = public.current_user_id());
