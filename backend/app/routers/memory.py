from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from plugins import memory as mem

from app.core.clients import genai_client, supabase
from app.core.deps import require_user
from app.schemas.memory import MemoryAdd

router = APIRouter()


@router.get("/api/memory")
async def memory_list(
    user: dict[str, Any] = Depends(require_user),
    kind: Optional[str] = None,
    limit: int = 100,
):
    q = (
        supabase.table("memory_embeddings")
        .select("id, content, kind, source_session, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(min(max(limit, 1), 500))
    )
    if kind:
        q = q.eq("kind", kind)
    res = q.execute()
    return {"memories": res.data or []}


@router.delete("/api/memory/{memory_id}")
async def memory_delete(memory_id: str, user: dict[str, Any] = Depends(require_user)):
    supabase.table("memory_embeddings").delete().eq("id", memory_id).eq(
        "user_id", user["id"]
    ).execute()
    return {"status": "deleted"}


@router.delete("/api/memory")
async def memory_wipe(user: dict[str, Any] = Depends(require_user)):
    supabase.table("memory_embeddings").delete().eq("user_id", user["id"]).execute()
    return {"status": "wiped"}


@router.post("/api/memory")
async def memory_add(body: MemoryAdd, user: dict[str, Any] = Depends(require_user)):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    try:
        vec = mem.embed_document(genai_client, content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"embed failed: {exc}") from exc
    mem.store(
        supabase,
        user_id=user["id"],
        content=content,
        embedding=vec,
        kind=body.kind,
    )
    return {"status": "added"}
