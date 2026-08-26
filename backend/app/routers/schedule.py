from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core import security as _sec
from app.core.clients import supabase
from app.core.config import FUNCTION_SECRET
from app.core.deps import require_user
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

from main import run_assistant, send_onesignal_notification, send_scheduled_task_email

logger = logging.getLogger("kin")

router = APIRouter()


@router.get("/api/schedule")
async def get_scheduled_tasks(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("scheduled_tasks").select("*").eq("user_id", user["id"]).execute()
        return res.data or []
    except Exception as e:
        logger.exception("Failed to query scheduled tasks")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/schedule")
async def create_schedule(body: ScheduleCreate, user: dict[str, Any] = Depends(require_user)):
    if body.channel not in ("web", "email"):
        raise HTTPException(status_code=400, detail="Channel must be either 'web' or 'email'.")

    try:
        from croniter import croniter
        croniter(body.cron_expression)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    try:
        import pytz
        pytz.timezone(body.timezone)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {e}")

    try:
        data = {
            "user_id": user["id"],
            "name": body.name,
            "prompt": body.prompt,
            "cron_expression": body.cron_expression,
            "timezone": body.timezone,
            "channel": body.channel,
            "is_active": True
        }
        res = supabase.table("scheduled_tasks").insert(data).execute()
        if res.data:
            return res.data[0]
        raise HTTPException(status_code=500, detail="Failed to create scheduled task")
    except Exception as e:
        logger.exception("Failed to create scheduled task")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/schedule/{task_id}")
async def update_schedule(task_id: str, body: ScheduleUpdate, user: dict[str, Any] = Depends(require_user)):
    res = supabase.table("scheduled_tasks").select("*").eq("id", task_id).eq("user_id", user["id"]).execute()
    task = res.data[0] if res.data else None
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.prompt is not None:
        update_data["prompt"] = body.prompt
    if body.cron_expression is not None:
        try:
            from croniter import croniter
            croniter(body.cron_expression)
            update_data["cron_expression"] = body.cron_expression
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")
    if body.timezone is not None:
        try:
            import pytz
            pytz.timezone(body.timezone)
            update_data["timezone"] = body.timezone
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {e}")
    if body.channel is not None:
        if body.channel not in ("web", "email"):
            raise HTTPException(status_code=400, detail="Channel must be either 'web' or 'email'.")
        update_data["channel"] = body.channel
    if body.is_active is not None:
        update_data["is_active"] = body.is_active

    if not update_data:
        return task

    try:
        update_data["updated_at"] = datetime.utcnow().isoformat()
        res = supabase.table("scheduled_tasks").update(update_data).eq("id", task_id).eq("user_id", user["id"]).execute()
        if res.data:
            return res.data[0]
        raise HTTPException(status_code=500, detail="Failed to update scheduled task")
    except Exception as e:
        logger.exception("Failed to update scheduled task")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/schedule/{task_id}")
async def delete_schedule(task_id: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("scheduled_tasks").delete().eq("id", task_id).eq("user_id", user["id"]).execute()
        return {"status": "deleted"}
    except Exception as e:
        logger.exception("Failed to delete scheduled task")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/schedule/{task_id}/test")
async def test_scheduled_task(task_id: str, user: dict[str, Any] = Depends(require_user)):
    res = supabase.table("scheduled_tasks").select("*").eq("id", task_id).eq("user_id", user["id"]).execute()
    task = res.data[0] if res.data else None
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    try:
        session_id = f"scheduled-test-{task['id']}"
        exec_text = (
            f"SCHEDULED REMINDER EXECUTION:\nTask Name: {task.get('name', 'Reminder')}\nPrompt: {task['prompt']}\n\n"
            "Instruction: Format and deliver a clean, direct, friendly reminder to the user. "
            "Include any relevant contact numbers or details concisely. Do NOT output technical diagnostic search reports or lists of missing items."
        )
        reply = (await run_assistant(
            user=user,
            text=exec_text,
            audio_bytes=None,
            audio_mime=None,
            source=task["channel"],
            session_id=session_id,
        ))["reply"]
        if task["channel"] == "email":
            try:
                subject = f"Scheduled Briefing: {task['name']}"
                await send_scheduled_task_email(user, subject, reply)
            except Exception as e:
                return {
                    "status": "warning",
                    "reply": reply,
                    "detail": f"Task run succeeded, but email could not be sent: {e}"
                }
        elif task["channel"] == "web":
            await send_onesignal_notification(
                user_id=user["id"],
                title=f"Briefing: {task['name']}",
                message=reply[:120] + "..." if len(reply) > 120 else reply
            )

        supabase.table("scheduled_tasks").update({
            "last_run_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", task["id"]).execute()
        return {"status": "success", "reply": reply}
    except Exception as e:
        logger.exception("Scheduled task test failed")
        raise HTTPException(status_code=500, detail=f"Task execution failed: {e}")


@router.post("/cron/execute-scheduled-tasks")
async def execute_scheduled_tasks(secret: Optional[str] = None):
    # /cron/* transport stays query-param-only: this URI is registered
    # verbatim in an external Cloud Scheduler job, outside this repo.
    _sec.require_shared_secret(secret, FUNCTION_SECRET)

    import pytz
    from croniter import croniter

    try:
        res = supabase.table("scheduled_tasks").select("*").eq("is_active", True).execute()
        tasks = res.data or []
    except Exception as e:
        logger.exception("Failed to query scheduled tasks")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    now_utc = datetime.now(timezone.utc)
    executed_count = 0

    for task in tasks:
        try:
            tz = pytz.timezone(task["timezone"])
        except Exception:
            tz = pytz.utc

        now_tz = now_utc.astimezone(tz)
        now_minute = now_tz.replace(second=0, microsecond=0)

        try:
            iter = croniter(task["cron_expression"], now_minute - timedelta(seconds=1))
            next_run = iter.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = tz.localize(next_run)
            is_due = (next_run.year == now_minute.year and
                      next_run.month == now_minute.month and
                      next_run.day == now_minute.day and
                      next_run.hour == now_minute.hour and
                      next_run.minute == now_minute.minute)
        except Exception:
            logger.exception("Failed to evaluate cron for task %s", task["id"])
            continue

        if not is_due:
            continue

        try:
            user_res = supabase.table("users").select("*").eq("id", task["user_id"]).execute()
            user_full = user_res.data[0] if user_res.data else None
            if not user_full:
                logger.warning("User %s not found for task %s", task["user_id"], task["id"])
                continue

            session_id = f"scheduled-{task['id']}"
            exec_text = (
                f"SCHEDULED REMINDER EXECUTION:\nTask Name: {task.get('name', 'Reminder')}\nPrompt: {task['prompt']}\n\n"
                "Instruction: Format and deliver a clean, direct, friendly reminder to the user. "
                "Include any relevant contact numbers or details concisely. Do NOT output technical diagnostic search reports or lists of missing items."
            )
            reply = (await run_assistant(
                user=user_full,
                text=exec_text,
                audio_bytes=None,
                audio_mime=None,
                source=task["channel"],
                session_id=session_id,
            ))["reply"]
            if task["channel"] == "email":
                try:
                    subject = f"Scheduled Briefing: {task['name']}"
                    await send_scheduled_task_email(user_full, subject, reply)
                except Exception:
                    logger.exception("Failed to send scheduled task email during execution")
            elif task["channel"] == "web":
                await send_onesignal_notification(
                    user_id=user_full["id"],
                    title=f"Briefing: {task['name']}",
                    message=reply[:120] + "..." if len(reply) > 120 else reply
                )

            supabase.table("scheduled_tasks").update({
                "last_run_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", task["id"]).execute()
            executed_count += 1

        except Exception:
            logger.exception("Execution failed for task %s", task["id"])

    return {"status": "success", "executed_count": executed_count}
