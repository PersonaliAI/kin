from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from plugins import google_integrations as g
from plugins import microsoft_integrations as ms

from app.core.clients import supabase
from app.core.config import FUNCTION_SECRET

from main import run_assistant, send_onesignal_notification, send_scheduled_task_email

logger = logging.getLogger("kin")

router = APIRouter()


@router.post("/admin/run-email-trigger-flows")
async def run_email_trigger_flows(secret: Optional[str] = None):
    """Poll every active email trigger for new matching mail since it was
    last checked, and fire the associated prompt when found.

    Called every minute by the "kin-flow-email" Cloud Scheduler job — that
    job has existed since 2026-05-17 hitting exactly this path, but nothing
    was ever implemented behind it (confirmed 404 in production logs).
    """
    if FUNCTION_SECRET and secret != FUNCTION_SECRET:
        raise HTTPException(status_code=403, detail="invalid secret")

    try:
        res = supabase.table("email_trigger_flows").select("*").eq("is_active", True).execute()
        triggers = res.data or []
    except Exception as e:
        logger.exception("Failed to query email_trigger_flows")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    fired_count = 0
    for trig in triggers:
        try:
            user_res = supabase.table("users").select("*").eq("id", trig["user_id"]).execute()
            user_full = user_res.data[0] if user_res.data else None
            if not user_full:
                continue

            cutoff_str = trig.get("last_checked_at")
            try:
                cutoff = datetime.fromisoformat((cutoff_str or "").replace("Z", "+00:00"))
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=timezone.utc)
            except Exception:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

            sender = trig.get("sender_filter")
            keyword = trig.get("keyword_filter")

            # Cast a wide net (last day) then filter precisely by timestamp
            # in Python — Gmail/Graph search only support day-granularity
            # date filters, which would re-match the same email on every
            # single one-minute poll within the same day otherwise.
            if trig["source"] == "gmail":
                if not user_full.get("google_access_token"):
                    continue
                query_parts = []
                if sender:
                    query_parts.append(f"from:({sender})")
                if keyword:
                    query_parts.append(keyword)
                query_parts.append("newer_than:1d")
                messages = await g.list_gmail_messages(
                    supabase, user_full, limit=20, query=" ".join(query_parts)
                )
                new_messages = [
                    m for m in messages
                    if m.get("received_at")
                    and datetime.fromisoformat(m["received_at"].replace("Z", "+00:00")) > cutoff
                ]
            else:  # outlook
                if not user_full.get("microsoft_access_token"):
                    continue
                search_query = keyword or ""
                messages = await ms.list_outlook_messages(
                    supabase, user_full, limit=20, query=search_query, max_days_old=1
                )
                if sender:
                    messages = [
                        m for m in messages
                        if sender.lower() in (m.get("from_email") or "").lower()
                    ]
                new_messages = [
                    m for m in messages
                    if m.get("received_at")
                    and datetime.fromisoformat(m["received_at"].replace("Z", "+00:00")) > cutoff
                ]

            if not new_messages:
                continue

            match = new_messages[0]
            trigger_prompt = (
                f"{trig['prompt']}\n\n"
                f"(Triggered by a new email — From: {match.get('from')}, "
                f"Subject: {match.get('subject')}, Snippet: {match.get('snippet')})"
            )
            session_id = f"trigger-{trig['id']}"
            reply = (await run_assistant(
                user=user_full,
                text=trigger_prompt,
                audio_bytes=None,
                audio_mime=None,
                source=trig["channel"],
                session_id=session_id,
            ))["reply"]
            if trig["channel"] == "email":
                try:
                    await send_scheduled_task_email(user_full, f"Trigger: {trig['name']}", reply)
                except Exception:
                    logger.exception("Failed to send trigger email")
            elif trig["channel"] == "web":
                await send_onesignal_notification(
                    user_id=user_full["id"],
                    title=f"Trigger: {trig['name']}",
                    message=reply[:120] + "..." if len(reply) > 120 else reply,
                )

            supabase.table("email_trigger_flows").update(
                {"last_checked_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", trig["id"]).execute()
            fired_count += 1
        except Exception:
            logger.exception("Trigger check failed for %s", trig.get("id"))

    return {"status": "success", "fired_count": fired_count, "checked": len(triggers)}
