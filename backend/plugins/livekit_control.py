"""LiveKit server-SDK helpers for dispatching calls to kin-voice-worker.

kin-voice-worker is a separate long-running service (see
D:\\Documents\\_personaliai\\kin-voice-worker) that registers one LiveKit
Agents entrypoint and serves every tenant's voice agent dynamically by
reading `job.metadata` at call time. This module is the kin-backend side of
that contract: it asks LiveKit to create a room + dispatch the worker's
agent, then (for outbound calls) adds a SIP participant to place the actual
phone call. Inbound calls skip create_dispatch — LiveKit's own SIP dispatch
rule (configured once, out of band, against the worker's `agent_name`)
handles that automatically.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# Must match the `agent_name` kin-voice-worker registers on its AgentServer.
VOICE_AGENT_NAME = os.environ.get("LIVEKIT_VOICE_AGENT_NAME", "kin-voice-agent")

# Which SIP trunk to dial out through, per managed telephony provider. Set
# once these trunks are created in the LiveKit project (see
# telephony_providers.py for the provisioning side).
OUTBOUND_TRUNK_IDS = {
    "twilio_managed": os.environ.get("LIVEKIT_TWILIO_OUTBOUND_TRUNK_ID", ""),
    "telnyx_managed": os.environ.get("LIVEKIT_TELNYX_OUTBOUND_TRUNK_ID", ""),
}


def configured() -> bool:
    return bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


async def place_outbound_call(
    *,
    voice_agent_id: str,
    telephony_provider: str,
    from_number: str,
    to_number: str,
    call_id: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch the shared worker agent into a fresh room, then bridge a SIP
    participant (the dialed phone number) into it. Mirrors the
    `dial_bank_agent.py` example from the livekit/agents repo."""
    if not configured():
        raise RuntimeError("LiveKit is not configured (LIVEKIT_URL/API_KEY/API_SECRET missing)")

    trunk_id = OUTBOUND_TRUNK_IDS.get(telephony_provider)
    if not trunk_id:
        raise RuntimeError(f"No outbound SIP trunk configured for provider '{telephony_provider}'")

    from livekit import api as lk_api

    room_name = f"voice-{voice_agent_id}-{call_id or os.urandom(4).hex()}"
    metadata = json.dumps({
        "voice_agent_id": voice_agent_id,
        "direction": "outbound",
        "to_number": to_number,
        "call_id": call_id,
    })

    lkapi = lk_api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lkapi.agent_dispatch.create_dispatch(
            lk_api.CreateAgentDispatchRequest(
                agent_name=VOICE_AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
        participant = await lkapi.sip.create_sip_participant(
            lk_api.CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=trunk_id,
                sip_call_to=to_number,
                sip_number=from_number,
                participant_identity=f"caller-{to_number}",
            )
        )
        return {"room_name": room_name, "participant_id": participant.participant_id}
    finally:
        await lkapi.aclose()
