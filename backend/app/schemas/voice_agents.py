from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class VoiceAgentCreate(BaseModel):
    name: str
    use_case: str = "custom"
    persona: str = ""
    greeting: Optional[str] = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    stt_provider: str = "deepgram"
    tts_provider: str = "cartesia"
    tts_voice: Optional[str] = None
    tools: list[str] = []
    # BYOK — each voice agent uses the owning user's own provider keys, not
    # a shared Kin-paid key. Plaintext in the request, encrypted at rest
    # (llm_providers.encrypt_api_key, same Fernet key as text-chat BYOK),
    # and only ever decrypted again inside /internal/voice-agents/{id}/config
    # for kin-voice-worker to use for that call.
    llm_api_key: Optional[str] = None
    stt_api_key: Optional[str] = None
    tts_api_key: Optional[str] = None


class VoiceAgentUpdate(BaseModel):
    name: Optional[str] = None
    use_case: Optional[str] = None
    persona: Optional[str] = None
    greeting: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    stt_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_voice: Optional[str] = None
    tools: Optional[list[str]] = None
    inbound_enabled: Optional[bool] = None
    status: Optional[str] = None
    llm_api_key: Optional[str] = None
    stt_api_key: Optional[str] = None
    tts_api_key: Optional[str] = None


class VoiceAgentProvisionNumber(BaseModel):
    telephony_provider: str  # twilio_managed | telnyx_managed
    phone_number: str  # chosen from a prior search-numbers call


class VoiceAgentTestCall(BaseModel):
    to_number: str


class InternalToolExecute(BaseModel):
    voice_agent_id: str
    tool_name: str
    args: dict[str, Any] = {}


class InternalVoiceCallEvent(BaseModel):
    voice_agent_id: str
    call_id: Optional[str] = None  # None on the first event -> we create the row
    direction: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    transcript: Optional[list[dict[str, Any]]] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    status: Optional[str] = None  # in_progress | completed | failed
    ended: bool = False
