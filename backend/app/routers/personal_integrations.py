from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from plugins import google_integrations as g
from plugins import microsoft_integrations as ms

from app.core.clients import supabase
from app.core.deps import require_user
from app.schemas.personal_integrations import (
    ExternalTaskToggleBody,
    GoogleContactBody,
    MicrosoftContactBody,
)

from main import _decode_state, _mint_state, plan_for

logger = logging.getLogger("kin")

router = APIRouter()

# Pro/Executive can connect this many EXTRA Google accounts on top of their
# primary one (real version of the old "up to 3 connected accounts" claim —
# see kin_connected_accounts migration + agent_tools._read_gmail/_read_calendar).
MAX_EXTRA_GOOGLE_ACCOUNTS: dict[str, int] = {"pro": 2, "executive": 2}


@router.post("/api/integrations/google/start")
async def google_start(
    request: Request,
    redirect_path: Optional[str] = None,
    mode: str = "primary",
    user: dict[str, Any] = Depends(require_user)
):
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")
    if mode == "add":
        cap = MAX_EXTRA_GOOGLE_ACCOUNTS.get(plan_for(user), 0)
        if cap <= 0:
            raise HTTPException(
                status_code=403,
                detail="Connecting extra Google accounts is a Pro+ feature. Upgrade at /dashboard/billing.",
            )
        existing = (
            supabase.table("kin_connected_accounts")
            .select("id", count="exact", head=True)
            .eq("user_id", user["id"])
            .execute()
        )
        if (existing.count or 0) >= cap:
            raise HTTPException(
                status_code=400,
                detail=f"You've reached the limit of {cap} extra connected account(s) on your plan.",
            )
    origin = request.headers.get("origin", "")
    if not redirect_path:
        redirect_path = "/dashboard" if "chatty" in origin or "localhost:3001" in origin else "/dashboard/integrations"
    state = _mint_state(user["auth_user_id"], origin_url=origin, redirect_path=redirect_path, mode=mode)
    # g.auth_url already sets prompt=consent, so Google always reissues a
    # refresh token here — needed so "add another account" doesn't end up
    # depending on a token minted for a different connection.
    return {"url": g.auth_url(state)}


@router.get("/auth/google/callback")
async def google_callback(code: str, state: str):
    auth_user_id, frontend, redirect_path, mode = _decode_state(state)
    if not auth_user_id:
        return RedirectResponse(f"{frontend}{redirect_path}?google=error")

    try:
        tokens = await g.exchange_code(code)
    except httpx.HTTPError as exc:
        logger.exception("google token exchange failed")
        return RedirectResponse(f"{frontend}{redirect_path}?google=error")

    access = tokens["access_token"]
    refresh = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 3600))
    scope = tokens.get("scope", "")

    profile: dict[str, Any] = {}
    try:
        profile = await g.userinfo(access)
    except httpx.HTTPError:
        pass

    if mode == "add":
        if not refresh:
            # Google only issues a refresh token on first consent; the
            # prompt=consent param above should prevent this, but bail
            # cleanly rather than store an unrefreshable extra account.
            return RedirectResponse(f"{frontend}{redirect_path}?google=error")
        user_res = supabase.table("users").select("id, plan").eq("auth_user_id", auth_user_id).execute()
        if not user_res.data:
            return RedirectResponse(f"{frontend}{redirect_path}?google=error")
        owner = user_res.data[0]
        cap = MAX_EXTRA_GOOGLE_ACCOUNTS.get(plan_for(owner), 0)
        existing = (
            supabase.table("kin_connected_accounts")
            .select("id", count="exact", head=True)
            .eq("user_id", owner["id"])
            .execute()
        )
        if cap <= 0 or (existing.count or 0) >= cap:
            return RedirectResponse(f"{frontend}{redirect_path}?google=error")
        supabase.table("kin_connected_accounts").insert({
            "user_id": owner["id"],
            "google_access_token": access,
            "google_refresh_token": refresh,
            "google_token_expiry": (
                datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
            ).isoformat(),
            "google_scopes": scope,
            "google_email": profile.get("email"),
        }).execute()
        return RedirectResponse(f"{frontend}{redirect_path}?google=added")

    update: dict[str, Any] = {
        "google_access_token": access,
        "google_token_expiry": (
            datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat(),
        "google_scopes": scope,
        "google_email": profile.get("email"),
    }
    if refresh:
        update["google_refresh_token"] = refresh

    supabase.table("users").update(update).eq("auth_user_id", auth_user_id).execute()
    return RedirectResponse(f"{frontend}{redirect_path}?google=ok")


@router.post("/api/integrations/google/disconnect")
async def google_disconnect(user: dict[str, Any] = Depends(require_user)):
    supabase.table("users").update(
        {
            "google_access_token": None,
            "google_refresh_token": None,
            "google_token_expiry": None,
            "google_email": None,
            "google_scopes": None,
        }
    ).eq("id", user["id"]).execute()
    return {"status": "disconnected"}


@router.get("/api/integrations/google/accounts")
async def list_extra_google_accounts(user: dict[str, Any] = Depends(require_user)):
    cap = MAX_EXTRA_GOOGLE_ACCOUNTS.get(plan_for(user), 0)
    res = (
        supabase.table("kin_connected_accounts")
        .select("id, label, google_email, created_at")
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    )
    accounts = res.data or []
    return {"accounts": accounts, "max": cap, "used": len(accounts)}


@router.delete("/api/integrations/google/accounts/{account_id}")
async def disconnect_extra_google_account(account_id: str, user: dict[str, Any] = Depends(require_user)):
    supabase.table("kin_connected_accounts").delete().eq("id", account_id).eq(
        "user_id", user["id"]
    ).execute()
    return {"status": "disconnected"}


@router.get("/api/integrations/calendar/events")
async def calendar_events(user: dict[str, Any] = Depends(require_user)):
    now = datetime.now(tz=timezone.utc)
    end = now + timedelta(days=7)

    events = []
    google_connected = bool(user.get("google_access_token"))
    ms_connected = bool(user.get("microsoft_access_token"))

    if google_connected:
        try:
            g_events = await g.list_calendar_events(supabase, user, now - timedelta(hours=2), end)
            for e in g_events:
                e["source"] = "google"
            events.extend(g_events)
        except Exception:
            logger.exception("google calendar list failed")

    if ms_connected:
        try:
            ms_events = await ms.list_outlook_events(
                supabase, user, time_min=now - timedelta(hours=2), time_max=end
            )
            for e in ms_events:
                e["source"] = "microsoft"
            events.extend(ms_events)
        except Exception:
            logger.exception("microsoft calendar list failed")

    # Sort by start time ascending
    events.sort(key=lambda x: x.get("start") or "")
    return {
        "events": events,
        "connected": {
            "google": google_connected,
            "microsoft": ms_connected,
        },
    }


@router.get("/api/integrations/gmail/messages")
async def gmail_messages(user: dict[str, Any] = Depends(require_user)):
    messages = []
    google_connected = bool(user.get("google_access_token"))
    ms_connected = bool(user.get("microsoft_access_token"))

    if google_connected:
        try:
            g_msgs = await g.list_gmail_messages(supabase, user)
            for m in g_msgs:
                m["source"] = "google"
            messages.extend(g_msgs)
        except Exception:
            logger.exception("gmail list failed")

    if ms_connected:
        try:
            ms_msgs = await ms.list_outlook_messages(supabase, user)
            for m in ms_msgs:
                m["source"] = "microsoft"
            messages.extend(ms_msgs)
        except Exception:
            logger.exception("outlook list failed")

    # Sort by received_at descending
    messages.sort(key=lambda x: x.get("received_at") or "", reverse=True)
    return {
        "messages": messages,
        "connected": {
            "google": google_connected,
            "microsoft": ms_connected,
        },
    }


@router.get("/api/integrations/tasks")
async def unified_tasks(user: dict[str, Any] = Depends(require_user)):
    all_tasks = []
    google_connected = bool(user.get("google_access_token"))
    ms_connected = bool(user.get("microsoft_access_token"))

    # 1. Kin-local tasks
    try:
        res = (
            supabase.table("tasks")
            .select("*")
            .eq("user_id", user["id"])
            .order("due_date", desc=False)
            .execute()
        )
        for t in res.data or []:
            t["source"] = "kin"
            all_tasks.append(t)
    except Exception:
        logger.exception("kin tasks list failed")

    # 2. Google Tasks
    if google_connected:
        try:
            g_tasks = await g.list_google_tasks(supabase, user)
            for t in g_tasks:
                all_tasks.append(
                    {
                        "id": f"google-{t['id']}",
                        "source": "google",
                        "title": t["title"],
                        "description": t["notes"],
                        "status": "done" if t["status"] == "completed" else "todo",
                        "priority": "medium",
                        "due_date": t["due"],
                        "external_id": t["id"],
                    }
                )
        except Exception:
            logger.exception("google tasks list failed")

    # 3. Microsoft ToDo
    if ms_connected:
        try:
            ms_tasks = await ms.list_todo_tasks(supabase, user)
            for t in ms_tasks:
                status = "todo"
                if t["status"] == "completed":
                    status = "done"
                elif t["status"] == "inProgress":
                    status = "in_progress"

                all_tasks.append(
                    {
                        "id": f"microsoft-{t['id']}",
                        "source": "microsoft",
                        "title": t["title"],
                        "description": t["body"],
                        "status": status,
                        "priority": "medium",
                        "due_date": t["due"],
                        "external_id": t["id"],
                        "list_id": t.get("list_id"),
                    }
                )
        except Exception:
            logger.exception("microsoft todo tasks list failed")

    return {
        "tasks": all_tasks,
        "connected": {
            "google": google_connected,
            "microsoft": ms_connected,
        },
    }


@router.patch("/api/integrations/tasks/{source}/{external_id}")
async def toggle_external_task(
    source: str,
    external_id: str,
    body: ExternalTaskToggleBody,
    user: dict[str, Any] = Depends(require_user),
):
    """Mark a Google Task or Microsoft ToDo task done/not-done from the
    dashboard's unified task list. Kin-local tasks go through the normal
    Supabase `tasks` table update instead — this is only for the two
    external providers, whose completion state lives on Google/Microsoft's
    own servers rather than in our DB."""
    if source == "google":
        if not user.get("google_access_token"):
            raise HTTPException(status_code=400, detail="Google not connected")
        return await g.update_google_task(
            supabase, user, task_id=external_id, completed=body.completed
        )
    if source == "microsoft":
        if not user.get("microsoft_access_token"):
            raise HTTPException(status_code=400, detail="Microsoft not connected")
        if not body.list_id:
            raise HTTPException(status_code=400, detail="list_id is required for Microsoft tasks")
        return await ms.update_todo_task(
            supabase,
            user,
            task_id=external_id,
            list_id=body.list_id,
            completed=body.completed,
        )
    raise HTTPException(status_code=400, detail=f"Unknown task source: {source}")


@router.get("/api/integrations/contacts")
async def unified_contacts(user: dict[str, Any] = Depends(require_user)):
    # 1. Kin contacts
    res = (
        supabase.table("contacts")
        .select("*")
        .eq("user_id", user["id"])
        .order("name")
        .execute()
    )
    kin_contacts = res.data or []
    for c in kin_contacts:
        c["source"] = "kin"

    # 2. External contacts
    external = []
    google_connected = bool(user.get("google_access_token"))
    ms_connected = bool(user.get("microsoft_access_token"))

    if google_connected:
        try:
            g_contacts = await g.list_google_contacts(supabase, user)
            for c in g_contacts:
                c["source"] = "google"
            external.extend(g_contacts)
        except Exception:
            logger.exception("google contacts list failed")

    if ms_connected:
        try:
            ms_contacts = await ms.list_outlook_contacts(supabase, user)
            for c in ms_contacts:
                c["source"] = "microsoft"
            external.extend(ms_contacts)
        except Exception:
            logger.exception("microsoft contacts list failed")

    return {
        "kin": kin_contacts,
        "external": external,
        "connected": {
            "google": google_connected,
            "microsoft": ms_connected,
        },
    }


@router.post("/api/integrations/microsoft/start")
async def microsoft_start(
    request: Request,
    redirect_path: Optional[str] = None,
    user: dict[str, Any] = Depends(require_user)
):
    if not os.environ.get("MICROSOFT_CLIENT_ID"):
        raise HTTPException(status_code=500, detail="MICROSOFT_CLIENT_ID not configured")
    origin = request.headers.get("origin", "")
    if not redirect_path:
        redirect_path = "/dashboard" if "chatty" in origin or "localhost:3001" in origin else "/dashboard/integrations"
    state = _mint_state(user["auth_user_id"], origin_url=origin, redirect_path=redirect_path)
    return {"url": ms.auth_url(state)}


@router.get("/auth/microsoft/callback")
async def microsoft_callback(code: str, state: str):
    auth_user_id, frontend, redirect_path, _mode = _decode_state(state)
    if not auth_user_id:
        return RedirectResponse(f"{frontend}{redirect_path}?microsoft=error")
    try:
        tokens = await ms.exchange_code(code)
    except httpx.HTTPError:
        logger.exception("microsoft token exchange failed")
        return RedirectResponse(f"{frontend}{redirect_path}?microsoft=error")

    access = tokens["access_token"]
    refresh = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 3600))
    scope = tokens.get("scope", "")

    profile: dict[str, Any] = {}
    try:
        profile = await ms.me(access)
    except httpx.HTTPError:
        pass

    update: dict[str, Any] = {
        "microsoft_access_token": access,
        "microsoft_token_expiry": (
            datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat(),
        "microsoft_scopes": scope,
        "microsoft_email": profile.get("mail") or profile.get("userPrincipalName"),
    }
    if refresh:
        update["microsoft_refresh_token"] = refresh
    supabase.table("users").update(update).eq("auth_user_id", auth_user_id).execute()
    return RedirectResponse(f"{frontend}{redirect_path}?microsoft=ok")


@router.post("/api/integrations/microsoft/disconnect")
async def microsoft_disconnect(user: dict[str, Any] = Depends(require_user)):
    supabase.table("users").update(
        {
            "microsoft_access_token": None,
            "microsoft_refresh_token": None,
            "microsoft_token_expiry": None,
            "microsoft_email": None,
            "microsoft_scopes": None,
        }
    ).eq("id", user["id"]).execute()
    return {"status": "disconnected"}


@router.get("/api/google/contacts")
async def google_contacts_list(
    user: dict[str, Any] = Depends(require_user),
    query: str = "",
    limit: int = 50,
):
    google_connected = bool(user.get("google_access_token"))
    ms_connected = bool(user.get("microsoft_access_token"))

    if not google_connected and not ms_connected:
        return {"connected": False, "contacts": []}

    all_contacts = []

    if google_connected:
        try:
            g_contacts = await g.list_google_contacts(
                supabase, user, query=query, limit=min(max(limit, 1), 100)
            )
            for c in g_contacts:
                c["source"] = "google"
            all_contacts.extend(g_contacts)
        except Exception:
            logger.exception("google contacts list failed")

    if ms_connected:
        try:
            # Microsoft contacts list helper
            ms_contacts = await ms.list_outlook_contacts(supabase, user, limit=limit)
            if query:
                q = query.lower()
                ms_contacts = [
                    c
                    for c in ms_contacts
                    if q in c.get("name", "").lower()
                    or any(q in e.lower() for e in c.get("emails", []))
                ]
            for c in ms_contacts:
                c["source"] = "microsoft"
                # Normalize for frontend GoogleContact type
                c["resource_name"] = c.get("id")
                c["title"] = c.get("job_title")
            all_contacts.extend(ms_contacts)
        except Exception:
            logger.exception("microsoft contacts list failed")

    # Sort by name
    all_contacts.sort(key=lambda x: x.get("name") or "")
    return {"connected": True, "contacts": all_contacts}


@router.post("/api/google/contacts")
async def google_contacts_create(
    body: GoogleContactBody, user: dict[str, Any] = Depends(require_user)
):
    if not user.get("google_access_token"):
        raise HTTPException(status_code=400, detail="Google not connected")
    return await g.create_google_contact(
        supabase,
        user,
        name=body.name,
        email=body.email,
        phone=body.phone,
        company=body.company,
        notes=body.notes,
    )


@router.post("/api/microsoft/contacts")
async def microsoft_contacts_create(
    body: MicrosoftContactBody, user: dict[str, Any] = Depends(require_user)
):
    if not user.get("microsoft_access_token"):
        raise HTTPException(status_code=400, detail="Microsoft not connected")
    created = await ms.create_outlook_contact(
        supabase,
        user,
        name=body.name,
        email=body.email,
        phone=body.phone,
        company=body.company,
    )
    # Normalize to match the frontend's GoogleContact shape, same as the
    # list endpoint above (resource_name/source aren't native Graph fields).
    created["source"] = "microsoft"
    created["resource_name"] = created.get("id")
    created["title"] = created.get("job_title")
    return created
