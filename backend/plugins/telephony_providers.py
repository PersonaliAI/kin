"""Managed phone-number provisioning for voice agents (Twilio / Telnyx).

Scope: search + buy a number and attach it to the SIP trunk that's already
wired to LiveKit (LIVEKIT_TWILIO_OUTBOUND_TRUNK_ID / _TELNYX_ variants in
livekit_control.py). Creating the SIP trunk itself, and the LiveKit inbound
SIP dispatch rule that routes calls on it to kin-voice-worker's agent_name,
are one-time infra steps done out of band (Twilio/Telnyx console + `lk sip`
CLI) — not something a per-user API call should be doing.

Plain httpx + each provider's REST API is used here rather than pulling in
the twilio/telnyx SDKs, to keep this consistent with how the rest of
kin-backend talks to external HTTP APIs (see google_integrations.py).
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_TRUNK_SID = os.environ.get("TWILIO_SIP_TRUNK_SID", "")

TELNYX_API_KEY = os.environ.get("TELNYX_API_KEY", "")
TELNYX_CONNECTION_ID = os.environ.get("TELNYX_SIP_CONNECTION_ID", "")


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_TRUNK_SID)


def telnyx_configured() -> bool:
    return bool(TELNYX_API_KEY and TELNYX_CONNECTION_ID)


async def search_twilio_numbers(country: str = "US", area_code: Optional[str] = None) -> list[dict[str, Any]]:
    if not twilio_configured():
        raise RuntimeError("Twilio is not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/SIP_TRUNK_SID missing)")
    params = {"VoiceEnabled": "true", "Limit": "10"}
    if area_code:
        params["AreaCode"] = area_code
    async with httpx.AsyncClient(auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=20.0) as client:
        resp = await client.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/AvailablePhoneNumbers/{country}/Local.json",
            params=params,
        )
        resp.raise_for_status()
        return [
            {"phone_number": n["phone_number"], "locality": n.get("locality"), "region": n.get("region")}
            for n in resp.json().get("available_phone_numbers", [])
        ]


async def purchase_twilio_number(phone_number: str) -> dict[str, Any]:
    """Buys the number, then attaches it to the pre-configured SIP trunk so
    inbound calls route to LiveKit."""
    if not twilio_configured():
        raise RuntimeError("Twilio is not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/SIP_TRUNK_SID missing)")
    async with httpx.AsyncClient(auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=20.0) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers.json",
            data={"PhoneNumber": phone_number},
        )
        resp.raise_for_status()
        number_sid = resp.json()["sid"]

        trunk_resp = await client.post(
            f"https://trunking.twilio.com/v1/Trunks/{TWILIO_TRUNK_SID}/PhoneNumbers",
            data={"PhoneNumberSid": number_sid},
        )
        trunk_resp.raise_for_status()
    return {"phone_number": phone_number, "provider_ref": number_sid}


async def search_telnyx_numbers(country: str = "US", area_code: Optional[str] = None) -> list[dict[str, Any]]:
    if not telnyx_configured():
        raise RuntimeError("Telnyx is not configured (TELNYX_API_KEY/SIP_CONNECTION_ID missing)")
    filters = {"filter[country_code]": country, "filter[features][]": "voice", "filter[limit]": 10}
    if area_code:
        filters["filter[national_destination_code]"] = area_code
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}, timeout=20.0) as client:
        resp = await client.get("https://api.telnyx.com/v2/available_phone_numbers", params=filters)
        resp.raise_for_status()
        return [
            {"phone_number": n["phone_number"], "locality": n.get("region_information", [{}])[0].get("region_name")}
            for n in resp.json().get("data", [])
        ]


async def purchase_telnyx_number(phone_number: str) -> dict[str, Any]:
    if not telnyx_configured():
        raise RuntimeError("Telnyx is not configured (TELNYX_API_KEY/SIP_CONNECTION_ID missing)")
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}, timeout=20.0) as client:
        order_resp = await client.post(
            "https://api.telnyx.com/v2/number_orders",
            json={"phone_numbers": [{"phone_number": phone_number}]},
        )
        order_resp.raise_for_status()

        assign_resp = await client.post(
            "https://api.telnyx.com/v2/number_assignments",
            json={"phone_numbers": [phone_number], "connection_id": TELNYX_CONNECTION_ID},
        )
        assign_resp.raise_for_status()
    return {"phone_number": phone_number, "provider_ref": order_resp.json().get("data", {}).get("id")}
