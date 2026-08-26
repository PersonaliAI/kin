"""Lemon Squeezy subscription webhook.

main.py's module docstring has claimed since before this router split that
the backend "Handles Lemon Squeezy webhooks (HMAC verified, idempotent)" —
that was never true. LEMON_WEBHOOK_SECRET/LEMON_API_KEY/LEMON_STORE_ID/
LEMON_VARIANT_TO_PLAN were all imported into main.py and never referenced
again anywhere. Subscription state (users.plan, subscription_status,
subscription_renews_at, subscription_variant_id, lemon_customer_id,
lemon_subscription_id) and the idempotency table (lemon_events) already
existed in the schema (20260511120000_slice2_billing_and_integrations.sql,
20260719000000_chatty_billing_plans.sql) waiting for this handler — this
file is the first thing that actually writes to them from a webhook.

IMPORTANT — this needs real manual testing before anyone trusts it in
production:
  * Verified against Lemon Squeezy's documented webhook shape and signing
    scheme (X-Signature: hex HMAC-SHA256 of the raw body, using the
    webhook's signing secret), but never exercised against a real delivery.
  * Lemon Squeezy webhook payloads do not carry an application-level unique
    event/delivery id in the body; idempotency here is keyed on a SHA-256
    hash of the raw body, which correctly dedupes exact-retry redelivery
    (Lemon Squeezy resends the identical payload on retry) but should be
    re-verified against real payloads/retry behavior.
  * Attributing an incoming event to a Kin user relies on
    meta.custom_data.user_id being set at Checkout creation — but no
    checkout-session-creation code exists anywhere in this repository
    (LEMON_API_KEY/LEMON_STORE_ID are otherwise unused too), so nothing
    currently populates that custom data. Until checkout creation is built
    and passes custom_data={"user_id": <users.id>}, only
    subscription_updated/cancelled/etc. events for an ALREADY-linked
    subscriber (matched by lemon_customer_id / lemon_subscription_id) can
    be attributed — a fresh subscription_created for a brand-new customer
    with no prior link cannot be, and is logged + skipped rather than
    guessed at.
  * Test against Lemon Squeezy's webhook test/replay tool
    (dashboard > Settings > Webhooks > "..." > Resend, or their test-mode
    events) before relying on this for real billing state.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.clients import supabase
from app.core.config import LEMON_VARIANT_TO_PLAN, LEMON_WEBHOOK_SECRET

logger = logging.getLogger("kin")

router = APIRouter()

# Events that move a subscription into an "in good standing, apply the
# variant's plan" state.
_PLAN_APPLYING_EVENTS = {
    "subscription_created",
    "subscription_updated",
    "subscription_resumed",
    "subscription_unpaused",
}
# Events that end access — downgrade to free once the subscription is truly
# over (vs. "cancelled", which Lemon Squeezy still leaves active until the
# end of the current billing period).
_EXPIRING_EVENTS = {"subscription_expired"}
_CANCELLING_EVENTS = {"subscription_cancelled"}
_PAUSING_EVENTS = {"subscription_paused"}
# Recognized but not acted on beyond idempotent logging — see module
# docstring: payment-event payload shape wasn't verified against a real
# delivery, and subscription_updated already carries status transitions
# for the cases that matter to plan gating.
_LOGGED_ONLY_EVENTS = {
    "subscription_payment_success",
    "subscription_payment_failed",
    "subscription_payment_recovered",
    "subscription_payment_refunded",
    "order_created",
    "order_refunded",
}


def _verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not LEMON_WEBHOOK_SECRET or not signature_header:
        return False
    expected = hmac.new(LEMON_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, signature_header)
    except (TypeError, ValueError):
        return False


def _find_user_by_customer_or_subscription(customer_id: Optional[str], subscription_id: Optional[str]) -> Optional[dict[str, Any]]:
    if subscription_id:
        res = supabase.table("users").select("*").eq("lemon_subscription_id", str(subscription_id)).limit(1).execute()
        if res.data:
            return res.data[0]
    if customer_id:
        res = supabase.table("users").select("*").eq("lemon_customer_id", str(customer_id)).limit(1).execute()
        if res.data:
            return res.data[0]
    return None


def _find_user_by_custom_data(custom_data: dict[str, Any]) -> Optional[dict[str, Any]]:
    user_id = custom_data.get("user_id")
    if not user_id:
        return None
    res = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
    return res.data[0] if res.data else None


@router.post("/webhooks/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-signature")
    if not _verify_signature(raw_body, signature):
        # Deliberately generic detail — don't tell a probing caller whether
        # the secret is unset vs. the signature just didn't match.
        raise HTTPException(status_code=403, detail="invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    # Idempotency: Lemon Squeezy payloads carry no application-level event
    # id, but retries resend byte-identical bodies, so a hash of the raw
    # body is a correct dedupe key for retry redelivery (see module
    # docstring for the caveat about two genuinely-different events that
    # happen to serialize identically, which should not occur in practice).
    event_id = hashlib.sha256(raw_body).hexdigest()
    meta = payload.get("meta") or {}
    event_name = meta.get("event_name") or "unknown"

    existing = supabase.table("lemon_events").select("event_id").eq("event_id", event_id).maybe_single().execute()
    if existing.data:
        logger.info("lemonsqueezy webhook %s (%s) already processed, skipping", event_id, event_name)
        return JSONResponse({"status": "duplicate", "event_id": event_id})

    data = payload.get("data") or {}
    attrs = data.get("attributes") or {}
    custom_data = meta.get("custom_data") or {}

    subscription_id = data.get("id") if data.get("type") == "subscriptions" else attrs.get("subscription_id")
    customer_id = attrs.get("customer_id")
    variant_id = attrs.get("variant_id")

    user = _find_user_by_custom_data(custom_data) or _find_user_by_customer_or_subscription(
        str(customer_id) if customer_id is not None else None,
        str(subscription_id) if subscription_id is not None else None,
    )

    if not user:
        logger.warning(
            "lemonsqueezy webhook %s (%s): could not attribute to a Kin user "
            "(no custom_data.user_id, no matching lemon_customer_id/lemon_subscription_id) — "
            "skipping plan update, recording for idempotency only",
            event_id, event_name,
        )
    else:
        update: dict[str, Any] = {}
        if subscription_id is not None:
            update["lemon_subscription_id"] = str(subscription_id)
        if customer_id is not None:
            update["lemon_customer_id"] = str(customer_id)
        if variant_id is not None:
            update["subscription_variant_id"] = str(variant_id)
        if attrs.get("renews_at"):
            update["subscription_renews_at"] = attrs["renews_at"]

        if event_name in _PLAN_APPLYING_EVENTS:
            update["subscription_status"] = attrs.get("status") or "active"
            plan = LEMON_VARIANT_TO_PLAN.get(str(variant_id)) if variant_id is not None else None
            if plan:
                update["plan"] = plan
            else:
                logger.warning(
                    "lemonsqueezy webhook %s (%s): variant_id %r has no entry in "
                    "LEMON_VARIANT_TO_PLAN — subscription status updated but plan left unchanged",
                    event_id, event_name, variant_id,
                )
        elif event_name in _CANCELLING_EVENTS:
            # Lemon Squeezy keeps access active until the period end even
            # after cancellation — record the status, don't downgrade yet.
            update["subscription_status"] = "cancelled"
        elif event_name in _PAUSING_EVENTS:
            update["subscription_status"] = "paused"
        elif event_name in _EXPIRING_EVENTS:
            update["subscription_status"] = "expired"
            update["plan"] = "free"
        elif event_name in _LOGGED_ONLY_EVENTS:
            logger.info("lemonsqueezy webhook %s (%s): logged, no plan mutation applied", event_id, event_name)
        else:
            logger.info("lemonsqueezy webhook %s: unrecognized event_name %r, logged only", event_id, event_name)

        if update:
            supabase.table("users").update(update).eq("id", user["id"]).execute()

    # Record for idempotency regardless of whether we could attribute a user
    # — a redelivered "couldn't attribute" event should still be a no-op.
    try:
        supabase.table("lemon_events").insert({
            "event_id": event_id,
            "event_name": event_name,
            "raw": payload,
        }).execute()
    except Exception:  # noqa: BLE001
        logger.exception("failed to record lemon_events row for %s", event_id)

    return JSONResponse({"status": "ok", "event_id": event_id, "event_name": event_name})
