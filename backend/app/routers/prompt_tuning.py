from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.clients import supabase
from app.core.config import MODEL_NAME
from app.core.deps import require_user
from app.core.llm import complete as llm_complete
from app.schemas.prompt_tuning import PromptTuningApply

from main import _require_executive

router = APIRouter()

# ---- Quarterly prompt tuning ------------------------------------------------

_PROMPT_TUNING_COOLDOWN_DAYS = 90


def _next_tuning_eligible_at(user: dict[str, Any]) -> Optional[datetime]:
    last = user.get("last_prompt_tuning_at")
    if not last:
        return None
    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    return last_dt + timedelta(days=_PROMPT_TUNING_COOLDOWN_DAYS)


@router.get("/api/kin/prompt-tuning/status")
async def prompt_tuning_status(user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    next_at = _next_tuning_eligible_at(user)
    eligible = next_at is None or datetime.now(timezone.utc) >= next_at
    return {"eligible": eligible, "next_eligible_at": next_at.isoformat() if next_at else None}


@router.post("/api/kin/prompt-tuning/suggest")
async def prompt_tuning_suggest(user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    next_at = _next_tuning_eligible_at(user)
    if next_at and datetime.now(timezone.utc) < next_at:
        raise HTTPException(
            status_code=429,
            detail=f"Prompt tuning is available once every {_PROMPT_TUNING_COOLDOWN_DAYS} days. "
                   f"Next eligible {next_at.date().isoformat()}.",
        )

    since = (datetime.now(timezone.utc) - timedelta(days=_PROMPT_TUNING_COOLDOWN_DAYS)).isoformat()
    hist = (
        supabase.table("messages")
        .select("role, content, created_at")
        .eq("user_id", user["id"])
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    rows = list(reversed(hist.data or []))
    transcript = "\n".join(
        f"{r['role']}: {(r.get('content') or '')[:400]}" for r in rows if r.get("content")
    )[-12000:]  # keep the prompt bounded regardless of history size

    if not transcript.strip():
        raise HTTPException(
            status_code=400,
            detail="Not enough recent conversation history to base a suggestion on yet.",
        )

    current_prompt = user.get("system_prompt") or ""
    tuning_prompt = (
        "You are tuning a personal AI assistant's custom system prompt based on "
        "how the user has actually been talking to it over the last quarter. "
        "Look for patterns: repeated corrections, a tone the user keeps asking "
        "for, topics they return to, instructions they've had to repeat. "
        "Propose a revised system prompt that would have made recent "
        "conversations go better, and a short rationale (2-4 sentences) "
        "explaining what you changed and why. Keep the assistant's core "
        "identity as 'Kin' intact.\n\n"
        f"CURRENT SYSTEM PROMPT:\n{current_prompt or '(none set — using the default)'}\n\n"
        f"RECENT CONVERSATION TRANSCRIPT (user/assistant turns):\n{transcript}\n\n"
        "Respond with exactly two sections, plain text:\n"
        "SUGGESTED_PROMPT:\n<the new system prompt text>\n\n"
        "RATIONALE:\n<2-4 sentences>"
    )
    resp = await llm_complete(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": tuning_prompt}],
        temperature=0.4,
        feature="prompt_tuning",
        user_id=user["id"],
    )
    text = (resp.text or "").strip()
    suggested, rationale = text, ""
    if "RATIONALE:" in text:
        head, _, tail = text.partition("RATIONALE:")
        suggested, rationale = head, tail.strip()
    suggested = suggested.replace("SUGGESTED_PROMPT:", "").strip()
    return {"suggested_prompt": suggested, "rationale": rationale}


@router.post("/api/kin/prompt-tuning/apply")
async def prompt_tuning_apply(body: PromptTuningApply, user: dict[str, Any] = Depends(require_user)):
    _require_executive(user)
    supabase.table("users").update({
        "system_prompt": body.system_prompt,
        "last_prompt_tuning_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user["id"]).execute()
    return {"status": "applied"}
