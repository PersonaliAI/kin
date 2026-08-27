-- Adds a "realtime" mode alongside the existing STT/LLM/TTS pipeline:
-- Gemini Live / OpenAI Realtime speech-to-speech models, no separate STT/TTS
-- stage. Reuses the existing llm_provider/llm_model/llm_api_key_encrypted
-- columns (provider = google|openai, model = the realtime model id) and
-- tts_voice (the realtime model's voice, e.g. "Puck"/"marin") rather than
-- adding new columns — stt_provider/tts_provider simply go unused when
-- mode = 'realtime'. See kin-voice-worker/worker.py's build_realtime().
ALTER TABLE voice_agents ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'pipeline';
ALTER TABLE voice_agents DROP CONSTRAINT IF EXISTS voice_agents_mode_check;
ALTER TABLE voice_agents ADD CONSTRAINT voice_agents_mode_check CHECK (mode IN ('pipeline', 'realtime'));
