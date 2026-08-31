-- Fixes a real perf bug in GET /api/usage: main.py's get_monthly_token_usage()
-- did `supabase.table("messages").select("prompt_tokens, completion_tokens,
-- total_tokens").eq("user_id", ...).gte("created_at", month_start).execute()`
-- with no LIMIT, then summed the three columns in Python — pulling every
-- message row from the whole month over PostgREST just to compute three
-- sums, for an endpoint the dashboard calls on effectively every page load
-- (UsageMeter). Worse, GET /api/usage called this function TWICE per request
-- (once directly, once via quota_state()), doubling the cost. An active
-- user with thousands of messages in a month made the usage/token-count UI
-- visibly slow to appear — exactly the reported symptom.
--
-- This does the SUM in Postgres instead (idx_messages_user_created_tokens,
-- added by 20260720030000, already covers the user_id/created_at filter) —
-- O(1) response payload regardless of message count. main.py is updated to
-- call this once via supabase.rpc() instead of two full-table-scan selects.
CREATE OR REPLACE FUNCTION kin_monthly_token_usage(p_user_id uuid, p_since timestamptz)
RETURNS TABLE (
  prompt_tokens bigint,
  completion_tokens bigint,
  total_tokens bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    COALESCE(SUM(m.prompt_tokens), 0)::bigint,
    COALESCE(SUM(m.completion_tokens), 0)::bigint,
    COALESCE(SUM(m.total_tokens), 0)::bigint
  FROM messages m
  WHERE m.user_id = p_user_id
    AND m.created_at >= p_since;
$$;
