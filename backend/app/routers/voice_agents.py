from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from plugins import agent_tools, livekit_control, llm_providers, telephony_providers

from app.core import security as _sec
from app.core.clients import genai_client, supabase
from app.core.config import FUNCTION_SECRET, MODEL_NAME
from app.core.deps import require_user
from app.schemas.voice_agents import (
    InternalToolExecute,
    InternalVoiceCallEvent,
    TwilioByokCredentials,
    VoiceAgentCreate,
    VoiceAgentProvisionNumber,
    VoiceAgentTestCall,
    VoiceAgentUpdate,
)

from main import _credentials_fernet, _decode_credentials_payload

logger = logging.getLogger("kin")

router = APIRouter()

# ---------------------------------------------------------------------------
# Voice Agents (LiveKit-powered sales / receptionist phone agents)
#
# Config lives in voice_agents / voice_agent_calls (see the
# 20260813000000_voice_agents.sql migration). Actual calls are handled by
# the separate kin-voice-worker service (LiveKit Agents), which is
# unauthenticated at the LiveKit layer but reads/writes config here through
# the /internal/* routes below, gated by FUNCTION_SECRET like /cron/*.
# ---------------------------------------------------------------------------

VOICE_AGENT_LLM_PROVIDERS = {"openai", "anthropic", "google", "xai"}
VOICE_AGENT_STT_PROVIDERS = {"deepgram", "google", "azure", "assemblyai", "openai"}
VOICE_AGENT_TTS_PROVIDERS = {"elevenlabs", "cartesia", "rime", "lmnt", "azure", "google"}
# Speech-to-speech models (audio in, audio out) — no separate STT/TTS stage.
# Only these two providers have a RealtimeModel in the installed LiveKit
# plugins (see kin-voice-worker/worker.py's build_realtime()).
VOICE_AGENT_REALTIME_PROVIDERS = {"google", "openai"}
VOICE_AGENT_MODES = {"pipeline", "realtime"}
VOICE_AGENT_USE_CASES = {"sales", "receptionist", "custom"}
VOICE_AGENT_TELEPHONY_PROVIDERS = {"twilio_managed", "telnyx_managed", "twilio_byok", "byo_sip"}


def _validate_voice_agent_fields(data: dict[str, Any]) -> None:
    if "use_case" in data and data["use_case"] not in VOICE_AGENT_USE_CASES:
        raise HTTPException(status_code=400, detail=f"use_case must be one of {sorted(VOICE_AGENT_USE_CASES)}")
    if "mode" in data and data["mode"] not in VOICE_AGENT_MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {sorted(VOICE_AGENT_MODES)}")
    is_realtime = data.get("mode") == "realtime"
    if "llm_provider" in data:
        allowed = VOICE_AGENT_REALTIME_PROVIDERS if is_realtime else VOICE_AGENT_LLM_PROVIDERS
        if data["llm_provider"] not in allowed:
            raise HTTPException(status_code=400, detail=f"llm_provider must be one of {sorted(allowed)}")
    # STT/TTS provider are unused in realtime mode — no need to validate them
    # (the pipeline-mode form doesn't submit them when the realtime tab is
    # active, so they just keep whatever value the row already had).
    if "stt_provider" in data and not is_realtime and data["stt_provider"] not in VOICE_AGENT_STT_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"stt_provider must be one of {sorted(VOICE_AGENT_STT_PROVIDERS)}")
    if "tts_provider" in data and not is_realtime and data["tts_provider"] not in VOICE_AGENT_TTS_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"tts_provider must be one of {sorted(VOICE_AGENT_TTS_PROVIDERS)}")


_VOICE_AGENT_KEY_FIELDS = {
    "llm_api_key": "llm_api_key_encrypted",
    "stt_api_key": "stt_api_key_encrypted",
    "tts_api_key": "tts_api_key_encrypted",
}


def _encrypt_voice_agent_keys(data: dict[str, Any]) -> None:
    """Pops plaintext BYOK fields out of `data` in place and replaces them
    with their encrypted-column equivalents. A blank string clears a
    previously-saved key; None (the default/unset case) leaves it alone."""
    for plain_field, enc_field in _VOICE_AGENT_KEY_FIELDS.items():
        if plain_field not in data:
            continue
        raw = data.pop(plain_field)
        if raw is None:
            continue
        data[enc_field] = llm_providers.encrypt_api_key(raw) if raw else None


def _mask_voice_agent(row: dict[str, Any]) -> dict[str, Any]:
    """Never let an encrypted key blob leave the API — the dashboard only
    needs to know whether a key is set, not its value."""
    row = dict(row)
    for plain_field, enc_field in _VOICE_AGENT_KEY_FIELDS.items():
        has_field = f"has_{plain_field}"
        row[has_field] = bool(row.get(enc_field))
        row.pop(enc_field, None)
    return row


@router.get("/api/voice-agents")
async def list_voice_agents(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("voice_agents").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
        return [_mask_voice_agent(row) for row in (res.data or [])]
    except Exception as e:
        logger.exception("Failed to query voice agents")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/voice-agents")
async def create_voice_agent(body: VoiceAgentCreate, user: dict[str, Any] = Depends(require_user)):
    data = body.model_dump()
    _validate_voice_agent_fields(data)
    _encrypt_voice_agent_keys(data)
    data["user_id"] = user["id"]
    try:
        res = supabase.table("voice_agents").insert(data).execute()
        if res.data:
            return _mask_voice_agent(res.data[0])
        raise HTTPException(status_code=500, detail="Failed to create voice agent")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create voice agent")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/voice-agents/{agent_id}")
async def update_voice_agent(agent_id: str, body: VoiceAgentUpdate, user: dict[str, Any] = Depends(require_user)):
    res = supabase.table("voice_agents").select("id").eq("id", agent_id).eq("user_id", user["id"]).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        return _mask_voice_agent(res.data[0])
    _validate_voice_agent_fields(update_data)
    _encrypt_voice_agent_keys(update_data)
    update_data["updated_at"] = datetime.utcnow().isoformat()

    try:
        res = supabase.table("voice_agents").update(update_data).eq("id", agent_id).eq("user_id", user["id"]).execute()
        if res.data:
            return _mask_voice_agent(res.data[0])
        raise HTTPException(status_code=500, detail="Failed to update voice agent")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update voice agent")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/voice-agents/{agent_id}")
async def delete_voice_agent(agent_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("voice_agents").delete().eq("id", agent_id).eq("user_id", user["id"]).execute()
        return {"status": "deleted"}
    except Exception as e:
        logger.exception("Failed to delete voice agent")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/voice-agents/{agent_id}/calls")
async def list_voice_agent_calls(agent_id: str, user: dict[str, Any] = Depends(require_user)):
    owns = supabase.table("voice_agents").select("id").eq("id", agent_id).eq("user_id", user["id"]).execute()
    if not owns.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    try:
        res = (
            supabase.table("voice_agent_calls")
            .select("*")
            .eq("voice_agent_id", agent_id)
            .order("started_at", desc=True)
            .limit(100)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query voice agent calls")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/voice-agents/{agent_id}/provision-number")
async def provision_voice_agent_number(agent_id: str, body: VoiceAgentProvisionNumber, user: dict[str, Any] = Depends(require_user)):
    if body.telephony_provider not in ("twilio_managed", "telnyx_managed", "twilio_byok"):
        raise HTTPException(status_code=400, detail="telephony_provider must be twilio_managed, telnyx_managed, or twilio_byok")
    owns = supabase.table("voice_agents").select("id").eq("id", agent_id).eq("user_id", user["id"]).execute()
    if not owns.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    byok_creds = None
    if body.telephony_provider == "twilio_byok":
        byok_creds = _get_twilio_byok_credentials(user["id"])
        if not byok_creds:
            raise HTTPException(status_code=400, detail="No Twilio credentials saved — add them in Settings → API Keys first.")

    supabase.table("voice_agents").update({"status": "provisioning"}).eq("id", agent_id).execute()
    try:
        if body.telephony_provider == "twilio_managed":
            result = await telephony_providers.purchase_twilio_number(body.phone_number)
        elif body.telephony_provider == "twilio_byok":
            result = await telephony_providers.purchase_twilio_number(body.phone_number, creds=byok_creds)
            # Attaches the new number to this user's LiveKit trunks + creates
            # its inbound dispatch rule — the managed/free path relies on a
            # dispatch rule the platform owner set up once, out of band;
            # BYOK numbers need one per number since each maps to a
            # different voice agent, so this has to happen per purchase.
            await livekit_control.register_byok_number(
                outbound_trunk_id=byok_creds["outbound_trunk_id"],
                inbound_trunk_id=byok_creds["inbound_trunk_id"],
                phone_number=result["phone_number"],
                voice_agent_id=agent_id,
            )
        else:
            result = await telephony_providers.purchase_telnyx_number(body.phone_number)
    except Exception as e:
        supabase.table("voice_agents").update({"status": "error"}).eq("id", agent_id).execute()
        logger.exception("Failed to provision voice agent number")
        raise HTTPException(status_code=502, detail=f"Number provisioning failed: {e}")

    res = supabase.table("voice_agents").update({
        "telephony_provider": body.telephony_provider,
        "phone_number": result["phone_number"],
        "status": "active",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", agent_id).execute()
    return res.data[0] if res.data else {"status": "active", "phone_number": result["phone_number"]}


@router.get("/api/voice-agents/available-numbers")
async def search_available_numbers(provider: str, country: str = "US", area_code: Optional[str] = None, user: dict[str, Any] = Depends(require_user)):
    if provider == "twilio_managed":
        return await telephony_providers.search_twilio_numbers(country, area_code)
    if provider == "telnyx_managed":
        return await telephony_providers.search_telnyx_numbers(country, area_code)
    if provider == "twilio_byok":
        byok_creds = _get_twilio_byok_credentials(user["id"])
        if not byok_creds:
            raise HTTPException(status_code=400, detail="No Twilio credentials saved — add them in Settings → API Keys first.")
        return await telephony_providers.search_twilio_numbers(country, area_code, creds=byok_creds)
    raise HTTPException(status_code=400, detail="provider must be twilio_managed, telnyx_managed, or twilio_byok")


@router.post("/api/voice-agents/{agent_id}/test-call")
async def test_call_voice_agent(agent_id: str, body: VoiceAgentTestCall, user: dict[str, Any] = Depends(require_user)):
    res = supabase.table("voice_agents").select("*").eq("id", agent_id).eq("user_id", user["id"]).execute()
    agent = res.data[0] if res.data else None
    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    if not agent.get("phone_number") or not agent.get("telephony_provider"):
        raise HTTPException(status_code=400, detail="Voice agent has no phone number provisioned yet")

    trunk_id_override = None
    if agent["telephony_provider"] == "twilio_byok":
        byok_creds = _get_twilio_byok_credentials(user["id"])
        trunk_id_override = byok_creds.get("outbound_trunk_id") if byok_creds else None
        if not trunk_id_override:
            raise HTTPException(
                status_code=400,
                detail="No Twilio credentials saved — add them in Settings → API Keys first.",
            )

    try:
        result = await livekit_control.place_outbound_call(
            voice_agent_id=agent_id,
            telephony_provider=agent["telephony_provider"],
            from_number=agent["phone_number"],
            to_number=body.to_number,
            trunk_id_override=trunk_id_override,
        )
        return {"status": "dialing", **result}
    except Exception as e:
        logger.exception("Failed to place test call")
        raise HTTPException(status_code=502, detail=f"Failed to place call: {e}")


@router.post("/api/voice-agents/{agent_id}/web-call")
async def web_test_call_voice_agent(agent_id: str, user: dict[str, Any] = Depends(require_user)):
    """Test a voice agent straight from the browser — no phone number or
    telephony provider required, unlike /test-call. Dispatches the same
    worker agent into a fresh LiveKit room and hands back a token the
    dashboard joins with livekit-client, mic-to-mic. This is what makes a
    voice agent testable the moment it's created, since number provisioning
    needs a configured Twilio/Telnyx account most users won't have yet."""
    owns = supabase.table("voice_agents").select("id").eq("id", agent_id).eq("user_id", user["id"]).execute()
    if not owns.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    try:
        result = await livekit_control.create_web_test_call(
            voice_agent_id=agent_id, user_identity=f"tester-{user['id']}",
        )
        return result
    except Exception as e:
        logger.exception("Failed to start web test call")
        raise HTTPException(status_code=502, detail=f"Failed to start test call: {e}")


def _get_provider_api_key(user_id: str, provider_slug: str) -> Optional[str]:
    try:
        res = supabase.table("user_credentials").select("encrypted_payload").eq("user_id", user_id).eq("integration_slug", provider_slug).maybe_single().execute()
        if res.data and res.data.get("encrypted_payload"):
            payload = _decode_credentials_payload(res.data["encrypted_payload"])
            return payload.get("api_key") or payload.get("apiKey")
    except Exception:
        logger.exception("Failed to decode user credentials for %s", provider_slug)
    return None


def _get_twilio_byok_credentials(user_id: str) -> Optional[dict[str, Any]]:
    """Saved via POST /api/voice-agents/telephony/twilio-byok (Settings' API
    Keys section calls this, not the generic /api/flow-credentials, since
    saving Twilio creds has a real side effect: auto-provisioning matching
    LiveKit SIP trunks). Same encrypted-payload storage as any other BYOK
    credential (user_credentials, integration_slug "twilio"), holding
    account_sid/auth_token/trunk_sid (the user's own Twilio values) plus
    outbound_trunk_id/inbound_trunk_id (the LiveKit trunks
    provision_byok_twilio_trunks created for them — the user never sees or
    enters these)."""
    try:
        res = supabase.table("user_credentials").select("encrypted_payload").eq("user_id", user_id).eq("integration_slug", "twilio").maybe_single().execute()
        if res.data and res.data.get("encrypted_payload"):
            payload = _decode_credentials_payload(res.data["encrypted_payload"])
            if payload.get("account_sid") and payload.get("auth_token") and payload.get("trunk_sid") and payload.get("outbound_trunk_id"):
                return payload
    except Exception:
        logger.exception("Failed to decode Twilio BYOK credentials for user %s", user_id)
    return None


@router.post("/api/voice-agents/telephony/twilio-byok")
async def save_twilio_byok_credentials(body: TwilioByokCredentials, user: dict[str, Any] = Depends(require_user)):
    """Saves the user's own Twilio credentials AND auto-provisions the
    matching LiveKit outbound/inbound SIP trunks in one step — the user
    never touches the LiveKit CLI or knows what a "trunk id" is. See
    livekit_control.provision_byok_twilio_trunks for exactly what gets
    created, and its docstring's note on this being verified against the
    real SDK but not against a live Twilio+LiveKit pair."""
    try:
        trunks = await livekit_control.provision_byok_twilio_trunks(
            user_id=user["id"],
            twilio_account_sid=body.account_sid,
            twilio_auth_token=body.auth_token,
            twilio_trunk_sid=body.trunk_sid,
        )
    except Exception as e:
        logger.exception("Failed to provision LiveKit trunks for Twilio BYOK")
        raise HTTPException(status_code=502, detail=f"Could not set up your Twilio account: {e}")

    payload = {
        "account_sid": body.account_sid,
        "auth_token": body.auth_token,
        "trunk_sid": body.trunk_sid,
        "outbound_trunk_id": trunks["outbound_trunk_id"],
        "inbound_trunk_id": trunks["inbound_trunk_id"],
    }
    try:
        ciphertext = _credentials_fernet().encrypt(json.dumps(payload).encode())
        supabase.table("user_credentials").upsert({
            "user_id": user["id"],
            "integration_slug": "twilio",
            "auth_type": "api_key",
            "encrypted_payload": f"\\x{ciphertext.hex()}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.exception("Failed to save Twilio BYOK credentials")
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success"}


@router.get("/internal/voice-agents/{agent_id}/config")
async def internal_get_voice_agent_config(request: Request, agent_id: str, secret: Optional[str] = None):
    """Fetched by kin-voice-worker at the start of every call (job.metadata
    carries this agent_id). Not user-JWT-gated — the worker has no logged-in
    user, only the shared FUNCTION_SECRET. Decrypts each BYOK provider key
    here (the worker never holds BYOK_ENCRYPTION_KEY) — this response only
    ever travels over the internal, secret-gated HTTPS call from the worker.

    /internal/* prefers `Authorization: Bearer <FUNCTION_SECRET>`; the
    `secret` query param still works as a fallback until kin-voice-worker is
    updated to send the header.

    No per-agent ownership check beyond the shared secret: `agent_id` is a
    `voice_agents.id` UUID (gen_random_uuid() primary key — see
    20260813000000_voice_agents.sql), not a guessable sequential ID, so this
    is not an enumerable IDOR on its own. The practical exposure is bounded
    by FUNCTION_SECRET leaking (addressed separately: hmac.compare_digest +
    fail-closed + header transport above), at which point ANY agent's
    decrypted BYOK keys are reachable — a real but secret-leak-gated risk,
    not an open one. If kin-voice-worker's dispatch context is ever changed
    to know which agent(s) it's legitimately allowed to fetch, add an
    explicit check here rather than relying on the secret alone.
    """
    _sec.require_shared_secret(_sec.resolve_gated_secret(request, secret), FUNCTION_SECRET)
    res = supabase.table("voice_agents").select("*").eq("id", agent_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    row = dict(res.data[0])
    for plain_field, enc_field in _VOICE_AGENT_KEY_FIELDS.items():
        encrypted = row.pop(enc_field, None)
        decrypted = llm_providers.decrypt_api_key(encrypted) if encrypted else None
        if not decrypted:
            provider_slug = None
            if plain_field == "llm_api_key":
                provider_slug = row.get("llm_provider")
            elif plain_field == "stt_api_key":
                provider_slug = row.get("stt_provider")
            elif plain_field == "tts_api_key":
                provider_slug = row.get("tts_provider")

            if provider_slug:
                decrypted = _get_provider_api_key(row["user_id"], provider_slug)
        row[plain_field] = decrypted
    return row


@router.post("/internal/voice-tools/execute")
async def internal_execute_voice_tool(request: Request, body: InternalToolExecute, secret: Optional[str] = None):
    """Runs a tool call made by a live voice-agent session, by reusing the
    exact same dispatcher (agent_tools.execute) the text chat surface uses —
    so calendar booking / lead creation / etc. behave identically on a phone
    call as they do in chat, with no reimplementation.

    /internal/* prefers `Authorization: Bearer <FUNCTION_SECRET>`; the
    `secret` query param still works as a fallback until kin-voice-worker is
    updated to send the header.
    """
    _sec.require_shared_secret(_sec.resolve_gated_secret(request, secret), FUNCTION_SECRET)

    agent_res = supabase.table("voice_agents").select("user_id, tools").eq("id", body.voice_agent_id).execute()
    if not agent_res.data:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    voice_agent = agent_res.data[0]

    if body.tool_name not in (voice_agent.get("tools") or []):
        raise HTTPException(status_code=403, detail=f"Tool '{body.tool_name}' is not enabled for this voice agent")

    user_res = supabase.table("users").select("*").eq("id", voice_agent["user_id"]).limit(1).execute()
    if not user_res.data:
        raise HTTPException(status_code=404, detail="Voice agent owner not found")
    user = user_res.data[0]

    result = await agent_tools.execute(
        body.tool_name,
        body.args,
        user=user,
        supabase=supabase,
        genai_client=genai_client,
        context={"source": "voice"},
    )
    return result


_CALL_OUTCOMES = {"lead_captured", "meeting_booked", "resolved", "no_action", "voicemail", "hung_up"}


async def _summarize_call(transcript: list[dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    """One-line summary + a coarse outcome tag for a finished call, so the
    dashboard's call history is actually useful to skim instead of showing
    only a timestamp and phone number. Best-effort: any failure here must
    never block the call from being marked ended (transcript is already
    saved regardless), so this always returns (None, None) rather than
    raising."""
    turns = [t for t in transcript if (t.get("text") or "").strip()]
    if len(turns) < 2:
        return None, None
    try:
        convo = "\n".join(f"{t.get('role', '?')}: {t['text'].strip()}" for t in turns[-40:])
        prompt = (
            "Summarize this phone call between an AI voice agent and a caller in ONE short "
            "sentence (under 20 words), then classify its outcome as exactly one of: "
            f"{', '.join(sorted(_CALL_OUTCOMES))}.\n\n"
            "Respond in EXACTLY this format, nothing else:\n"
            "SUMMARY: <one sentence>\n"
            "OUTCOME: <one tag>\n\n"
            f"Transcript:\n{convo}"
        )
        resp = await genai_client.aio.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = (resp.text or "").strip()
        summary: Optional[str] = None
        outcome: Optional[str] = None
        for line in text.splitlines():
            if line.upper().startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()[:300] or None
            elif line.upper().startswith("OUTCOME:"):
                tag = line.split(":", 1)[1].strip().lower()
                outcome = tag if tag in _CALL_OUTCOMES else None
        return summary, outcome
    except Exception:  # noqa: BLE001
        logger.exception("Call summary generation failed")
        return None, None


@router.post("/internal/voice-calls")
async def internal_upsert_voice_call(request: Request, body: InternalVoiceCallEvent, secret: Optional[str] = None):
    """kin-voice-worker posts a call-start event (no call_id) to open a log
    row, then further events (transcript/summary/end) keyed by the returned
    id, so the dashboard's call history stays live during a call.

    /internal/* prefers `Authorization: Bearer <FUNCTION_SECRET>`; the
    `secret` query param still works as a fallback until kin-voice-worker is
    updated to send the header.
    """
    _sec.require_shared_secret(_sec.resolve_gated_secret(request, secret), FUNCTION_SECRET)

    try:
        if not body.call_id:
            data = {
                "voice_agent_id": body.voice_agent_id,
                "direction": body.direction or "inbound",
                "from_number": body.from_number,
                "to_number": body.to_number,
                "status": "in_progress",
            }
            res = supabase.table("voice_agent_calls").insert(data).execute()
            return res.data[0]

        update_data: dict[str, Any] = {}
        if body.transcript is not None:
            update_data["transcript"] = body.transcript
        if body.summary is not None:
            update_data["summary"] = body.summary
        if body.outcome is not None:
            update_data["outcome"] = body.outcome
        if body.status is not None:
            update_data["status"] = body.status
        if body.ended:
            update_data["ended_at"] = datetime.utcnow().isoformat()
            update_data.setdefault("status", "completed")
            # worker.py's _on_shutdown never sets summary/outcome itself (it
            # only has the raw transcript, no LLM of its own to summarize
            # with) — generate them here so call history isn't just a
            # timestamp and phone number. Skipped if the caller already
            # supplied one of its own.
            if body.transcript and "summary" not in update_data and "outcome" not in update_data:
                summary, outcome = await _summarize_call(body.transcript)
                if summary:
                    update_data["summary"] = summary
                if outcome:
                    update_data["outcome"] = outcome

        if not update_data:
            res = supabase.table("voice_agent_calls").select("*").eq("id", body.call_id).execute()
            return res.data[0] if res.data else {"status": "noop"}

        res = supabase.table("voice_agent_calls").update(update_data).eq("id", body.call_id).execute()
        if res.data:
            return res.data[0]
        raise HTTPException(status_code=404, detail="Call log not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to record voice call event")
        raise HTTPException(status_code=500, detail=str(e))
