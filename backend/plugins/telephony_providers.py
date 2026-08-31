"""Phone-number provisioning for voice agents (Twilio / Telnyx).

Two ways a user gets a number:
  - **Managed (free)** — Kin's own shared Twilio/Telnyx account
    (TWILIO_ACCOUNT_SID/AUTH_TOKEN/SIP_TRUNK_SID env vars below). Zero setup
    for the user, but only available once the platform owner has configured
    those env vars and the matching LiveKit outbound trunk
    (LIVEKIT_TWILIO_OUTBOUND_TRUNK_ID in livekit_control.py).
  - **BYOK ("twilio_byok")** — the user's own Twilio account credentials,
    saved via the generic /api/flow-credentials mechanism under
    integration_slug "twilio" (see voice_agents.py's
    _get_twilio_byok_credentials). Every function below takes an optional
    `creds` override for this path; None falls back to the managed env vars.

Either way, creating the actual SIP trunk and registering it with LiveKit
(the `lk sip outbound create` / inbound dispatch-rule steps) stays a one-time
setup the account owner does out of band — for BYOK, the user does this
themselves against their own Twilio trunk and pastes the resulting LiveKit
trunk id into the same credentials form (see Settings' API Keys section) —
not something automated here, since it only needs to happen once per user,
not per call.

Plain httpx + each provider's REST API is used here rather than pulling in
the twilio/telnyx SDKs, to keep this consistent with how the rest of
kin-backend talks to external HTTP APIs (see google_integrations.py).
"""
from __future__ import annotations

import os
from typing import Any, Optional, TypedDict

import httpx

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_TRUNK_SID = os.environ.get("TWILIO_SIP_TRUNK_SID", "")

TELNYX_API_KEY = os.environ.get("TELNYX_API_KEY", "")
TELNYX_CONNECTION_ID = os.environ.get("TELNYX_SIP_CONNECTION_ID", "")


class TwilioCredentials(TypedDict):
    account_sid: str
    auth_token: str
    trunk_sid: str


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_TRUNK_SID)


def telnyx_configured() -> bool:
    return bool(TELNYX_API_KEY and TELNYX_CONNECTION_ID)


async def search_twilio_numbers(
    country: str = "US", area_code: Optional[str] = None, creds: Optional[TwilioCredentials] = None,
) -> list[dict[str, Any]]:
    account_sid = creds["account_sid"] if creds else TWILIO_ACCOUNT_SID
    auth_token = creds["auth_token"] if creds else TWILIO_AUTH_TOKEN
    if not (creds or twilio_configured()):
        raise RuntimeError("Twilio is not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/SIP_TRUNK_SID missing)")
    params = {"VoiceEnabled": "true", "Limit": "10"}
    if area_code:
        params["AreaCode"] = area_code
    async with httpx.AsyncClient(auth=(account_sid, auth_token), timeout=20.0) as client:
        resp = await client.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/AvailablePhoneNumbers/{country}/Local.json",
            params=params,
        )
        resp.raise_for_status()
        return [
            {"phone_number": n["phone_number"], "locality": n.get("locality"), "region": n.get("region")}
            for n in resp.json().get("available_phone_numbers", [])
        ]


async def purchase_twilio_number(phone_number: str, creds: Optional[TwilioCredentials] = None) -> dict[str, Any]:
    """Buys the number, then attaches it to the SIP trunk (managed or BYOK)
    so inbound calls route to LiveKit."""
    account_sid = creds["account_sid"] if creds else TWILIO_ACCOUNT_SID
    auth_token = creds["auth_token"] if creds else TWILIO_AUTH_TOKEN
    trunk_sid = creds["trunk_sid"] if creds else TWILIO_TRUNK_SID
    if not (creds or twilio_configured()):
        raise RuntimeError("Twilio is not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/SIP_TRUNK_SID missing)")
    async with httpx.AsyncClient(auth=(account_sid, auth_token), timeout=20.0) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
            data={"PhoneNumber": phone_number},
        )
        resp.raise_for_status()
        number_sid = resp.json()["sid"]

        trunk_resp = await client.post(
            f"https://trunking.twilio.com/v1/Trunks/{trunk_sid}/PhoneNumbers",
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
