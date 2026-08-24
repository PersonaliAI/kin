-- Voice Agents: AI phone agents (sales / receptionist) built on LiveKit
-- Agents. Config lives here; the actual call handling happens in the
-- separate kin-voice-worker service, which reads a row via
-- GET /internal/voice-agents/{id}/config (service-role only, no RLS access).

CREATE TABLE IF NOT EXISTS voice_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    use_case TEXT NOT NULL DEFAULT 'custom', -- sales | receptionist | custom
    persona TEXT NOT NULL DEFAULT '',        -- system prompt
    greeting TEXT,                           -- optional first line the agent speaks

    llm_provider TEXT NOT NULL DEFAULT 'openai',   -- openai | anthropic | google | groq | xai
    llm_model TEXT NOT NULL DEFAULT 'gpt-4o-mini',
    stt_provider TEXT NOT NULL DEFAULT 'deepgram',  -- deepgram | google | azure | assemblyai | openai
    tts_provider TEXT NOT NULL DEFAULT 'cartesia',  -- elevenlabs | cartesia | rime | lmnt | azure
    tts_voice TEXT,

    tools JSONB NOT NULL DEFAULT '[]'::jsonb, -- names from agent_tools.DECLARATIONS

    telephony_provider TEXT,      -- twilio_managed | telnyx_managed | byo_sip (null until chosen)
    phone_number TEXT,
    byo_sip_config JSONB,         -- encrypted trunk credentials (Fernet, BYOK_ENCRYPTION_KEY)

    status TEXT NOT NULL DEFAULT 'draft', -- draft | provisioning | active | paused | error
    inbound_enabled BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_voice_agents_user ON voice_agents(user_id);

ALTER TABLE voice_agents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage their own voice agents" ON voice_agents;
CREATE POLICY "Users manage their own voice agents" ON voice_agents
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Call log / transcript history. Written by kin-voice-worker via the
-- backend's service-role key only (POST /internal/voice-calls), surfaced to
-- the owner read-only via GET /api/voice-agents/{id}/calls — same
-- write-service-role / read-via-backend split as kin_webhook_deliveries.
CREATE TABLE IF NOT EXISTS voice_agent_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voice_agent_id UUID NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,

    direction TEXT NOT NULL,      -- inbound | outbound
    from_number TEXT,
    to_number TEXT,

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_seconds INT,

    transcript JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{role, text, ts}, ...]
    summary TEXT,
    outcome TEXT,                 -- e.g. "booked demo" | "voicemail" | "no answer"
    recording_url TEXT,

    status TEXT NOT NULL DEFAULT 'in_progress' -- in_progress | completed | failed
);
CREATE INDEX IF NOT EXISTS idx_voice_agent_calls_agent ON voice_agent_calls(voice_agent_id, started_at DESC);

ALTER TABLE voice_agent_calls ENABLE ROW LEVEL SECURITY;
