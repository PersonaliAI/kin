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
from datetime import timedelta
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
    trunk_id_override: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch the shared worker agent into a fresh room, then bridge a SIP
    participant (the dialed phone number) into it. Mirrors the
    `dial_bank_agent.py` example from the livekit/agents repo.

    `trunk_id_override` is for BYOK telephony ("twilio_byok"): there's no
    shared OUTBOUND_TRUNK_IDS entry for a per-user trunk, so the caller
    passes the LiveKit outbound trunk id the user registered against their
    own Twilio account (saved alongside their Twilio credentials — see
    voice_agents.py's _get_twilio_byok_credentials)."""
    if not configured():
        raise RuntimeError("LiveKit is not configured (LIVEKIT_URL/API_KEY/API_SECRET missing)")

    trunk_id = trunk_id_override or OUTBOUND_TRUNK_IDS.get(telephony_provider)
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


async def create_web_test_call(*, voice_agent_id: str, user_identity: str) -> dict[str, Any]:
    """Dispatch the worker agent into a fresh room and hand back a LiveKit
    access token so the dashboard itself (via livekit-client, no phone
    number involved) can join as the other participant — a "test in
    browser" call. Unlike place_outbound_call, there's no SIP participant:
    the caller IS the browser, connecting directly with its mic.

    This is what makes a voice agent actually testable before a phone
    number/telephony provider is configured at all — previously the only
    test path (test_call_voice_agent) required a provisioned number.
    """
    if not configured():
        raise RuntimeError("LiveKit is not configured (LIVEKIT_URL/API_KEY/API_SECRET missing)")

    from livekit import api as lk_api

    room_name = f"voice-test-{voice_agent_id}-{os.urandom(4).hex()}"
    metadata = json.dumps({
        "voice_agent_id": voice_agent_id,
        "direction": "web_test",
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
    finally:
        await lkapi.aclose()

    token = (
        lk_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(user_identity)
        .with_name(user_identity)
        .with_grants(lk_api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        .with_ttl(timedelta(minutes=10))  # a browser test call has no natural "hang up and re-dial" limit otherwise
        .to_jwt()
    )
    return {"room_name": room_name, "token": token, "url": LIVEKIT_URL}


async def provision_byok_twilio_trunks(
    *, user_id: str, twilio_account_sid: str, twilio_auth_token: str, twilio_trunk_sid: str,
) -> dict[str, str]:
    """Fully automates the LiveKit side of BYOK Twilio setup — the user only
    ever provides their own Twilio credentials; this looks up their Twilio
    trunk's SIP termination domain (Twilio Trunking API's own trunk
    resource) and registers matching outbound + inbound trunks with
    LiveKit. Field names/methods here (SIPOutboundTrunkInfo,
    CreateSIPInboundTrunkRequest, etc.) were confirmed against the actual
    installed livekit-api==1.2.0 package (its protobuf DESCRIPTOR.fields
    and method signatures), not guessed from docs — but the end-to-end
    call path (does a real Twilio number actually ring through these
    trunks) has not been exercised against live Twilio + LiveKit accounts
    in this environment. Verify with a real test call before relying on
    this for production traffic.

    Called once, when a user saves their Twilio BYOK credentials — see
    voice_agents.py's save_twilio_byok_credentials. Numbers are attached to
    these trunks later, per-purchase, by register_byok_number below (a
    user's Twilio account may have multiple numbers across multiple voice
    agents, sharing this one pair of trunks).
    """
    if not configured():
        raise RuntimeError("LiveKit is not configured (LIVEKIT_URL/API_KEY/API_SECRET missing)")

    import httpx

    async with httpx.AsyncClient(auth=(twilio_account_sid, twilio_auth_token), timeout=20.0) as client:
        resp = await client.get(f"https://trunking.twilio.com/v1/Trunks/{twilio_trunk_sid}")
        resp.raise_for_status()
        domain_name = resp.json().get("domain_name")
    if not domain_name:
        raise RuntimeError("Could not read this Twilio trunk's SIP termination domain — check the Trunk SID.")

    from livekit import api as lk_api

    lkapi = lk_api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        outbound = await lkapi.sip.create_sip_outbound_trunk(
            lk_api.CreateSIPOutboundTrunkRequest(
                trunk=lk_api.SIPOutboundTrunkInfo(
                    name=f"kin-byok-out-{user_id}",
                    address=domain_name,
                    numbers=[],  # numbers are added per purchase — see register_byok_number
                )
            )
        )
        inbound = await lkapi.sip.create_sip_inbound_trunk(
            lk_api.CreateSIPInboundTrunkRequest(
                trunk=lk_api.SIPInboundTrunkInfo(
                    name=f"kin-byok-in-{user_id}",
                    numbers=[],
                )
            )
        )
        return {"outbound_trunk_id": outbound.sip_trunk_id, "inbound_trunk_id": inbound.sip_trunk_id}
    finally:
        await lkapi.aclose()


async def register_byok_number(
    *, outbound_trunk_id: str, inbound_trunk_id: str, phone_number: str, voice_agent_id: str,
) -> None:
    """Called right after a BYOK Twilio number is purchased (see
    voice_agents.py's provision_voice_agent_number): adds the number to
    both LiveKit trunks and creates the inbound dispatch rule that
    auto-dispatches kin-voice-agent (via RoomAgentDispatch, baking
    voice_agent_id into the dispatch rule's own metadata — the same
    metadata shape entrypoint() in kin-voice-worker/worker.py already reads
    off ctx.job.metadata for outbound calls) into a fresh room whenever
    this specific number rings. For the managed/free path this same wiring
    is a one-time manual `lk sip` setup by the platform owner; here it's
    done per number, automatically, since each BYOK number belongs to a
    different voice agent.

    Existing numbers on each trunk are read back first and merged rather
    than overwritten — update_sip_*_trunk_fields sets `numbers` to exactly
    what's passed, so blindly passing [phone_number] would silently drop
    any other numbers already on the same user's trunks."""
    if not configured():
        raise RuntimeError("LiveKit is not configured (LIVEKIT_URL/API_KEY/API_SECRET missing)")

    from livekit import api as lk_api

    lkapi = lk_api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        out_list = await lkapi.sip.list_sip_outbound_trunk(lk_api.ListSIPOutboundTrunkRequest(trunk_ids=[outbound_trunk_id]))
        out_numbers = list(out_list.items[0].numbers) if out_list.items else []
        if phone_number not in out_numbers:
            out_numbers.append(phone_number)
        await lkapi.sip.update_sip_outbound_trunk_fields(outbound_trunk_id, numbers=out_numbers)

        in_list = await lkapi.sip.list_sip_inbound_trunk(lk_api.ListSIPInboundTrunkRequest(trunk_ids=[inbound_trunk_id]))
        in_numbers = list(in_list.items[0].numbers) if in_list.items else []
        if phone_number not in in_numbers:
            in_numbers.append(phone_number)
        await lkapi.sip.update_sip_inbound_trunk_fields(inbound_trunk_id, numbers=in_numbers)

        await lkapi.sip.create_sip_dispatch_rule(
            lk_api.CreateSIPDispatchRuleRequest(
                trunk_ids=[inbound_trunk_id],
                inbound_numbers=[phone_number],
                name=f"kin-byok-{voice_agent_id}",
                rule=lk_api.SIPDispatchRule(
                    dispatch_rule_individual=lk_api.SIPDispatchRuleIndividual(room_prefix=f"voice-{voice_agent_id}")
                ),
                room_config=lk_api.RoomConfiguration(
                    agents=[lk_api.RoomAgentDispatch(
                        agent_name=VOICE_AGENT_NAME,
                        metadata=json.dumps({"voice_agent_id": voice_agent_id, "direction": "inbound"}),
                    )],
                ),
            )
        )
    finally:
        await lkapi.aclose()
