-- Voice agent provider keys are bring-your-own (BYOK), per agent, not a
-- shared platform key — mirrors the existing BYOK pattern for text chat
-- (llm_providers.py's Fernet encrypt_api_key/decrypt_api_key, same
-- BYOK_ENCRYPTION_KEY). kin-voice-worker no longer reads provider keys
-- from its own environment; it receives the decrypted key per call from
-- kin-backend's /internal/voice-agents/{id}/config response.

ALTER TABLE voice_agents ADD COLUMN IF NOT EXISTS llm_api_key_encrypted TEXT;
ALTER TABLE voice_agents ADD COLUMN IF NOT EXISTS stt_api_key_encrypted TEXT;
ALTER TABLE voice_agents ADD COLUMN IF NOT EXISTS tts_api_key_encrypted TEXT;
