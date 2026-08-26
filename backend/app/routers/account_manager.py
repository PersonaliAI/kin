from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core import security as _sec
from app.core.clients import supabase
from app.core.deps import require_user
from app.schemas.account_manager import AccountManagerAssign

from main import _require_executive

router = APIRouter()

# ---- Dedicated account manager ---------------------------------------------
#
# No admin UI exists yet, so a named human is staffed via the internal
# assign endpoint below rather than SQL. Until assigned, Executive users see
# a real, working shared support contact (env-configured) instead of an
# empty card or a fabricated name.

_EXEC_SUPPORT_NAME = os.environ.get("EXECUTIVE_SUPPORT_NAME", "Kin Executive Support")
_EXEC_SUPPORT_EMAIL = os.environ.get("EXECUTIVE_SUPPORT_EMAIL", "support@personaliai.com")
_EXEC_SUPPORT_CALENDLY = os.environ.get("EXECUTIVE_SUPPORT_CALENDLY_URL", "")


@router.get("/api/kin/account-manager")
async def get_account_manager(user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    return {
        "name": user.get("account_manager_name") or _EXEC_SUPPORT_NAME,
        "email": user.get("account_manager_email") or _EXEC_SUPPORT_EMAIL,
        "calendly_url": user.get("account_manager_calendly_url") or _EXEC_SUPPORT_CALENDLY or None,
        "assigned": bool(user.get("account_manager_email")),
    }


@router.post("/api/admin/account-manager")
async def assign_account_manager(body: AccountManagerAssign, x_admin_secret: Optional[str] = Header(None)):
    """Internal-only: staffs a named account manager for one Executive user.
    Gated by a shared secret (ADMIN_SECRET env var), not a user session,
    since there's no admin panel/auth system to hook into yet."""
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    # Drive-by fix alongside the FUNCTION_SECRET remediation elsewhere: this
    # was already fail-closed (falsy admin_secret always denies), but used a
    # plain `!=` comparison — switched to the same constant-time helper used
    # for FUNCTION_SECRET, for consistency and to close the timing side
    # channel.
    _sec.require_shared_secret(x_admin_secret, admin_secret)
    supabase.table("users").update({
        "account_manager_name": body.name,
        "account_manager_email": body.email,
        "account_manager_calendly_url": body.calendly_url,
    }).eq("id", body.user_id).execute()
    return {"status": "assigned"}
