from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class SocialPostCreate(BaseModel):
    # social_account_ids is the multi-account path (one social_posts row is
    # created per id, sharing a group_id). integration_slug is kept as a
    # legacy fallback: if given with no social_account_ids, we resolve it to
    # that user's most-recently-connected account of that platform.
    integration_slug: Optional[str] = None
    social_account_ids: Optional[list[str]] = None
    content: str
    content_overrides: Optional[dict[str, str]] = None  # social_account_id -> override text
    publish_date: str # ISO-8601 string
    state: str = "queue" # queue, draft
    image_url: Optional[str] = None
    parent_post_id: Optional[str] = None
    settings: Optional[dict[str, Any]] = None  # per-platform post options (privacy, visibility, ...)
    repeat_interval: Optional[str] = None  # "daily" | "weekly" | "monthly"
    repeat_count: Optional[int] = None  # total occurrences including the first, capped at 12


class SocialPostUpdate(BaseModel):
    content: Optional[str] = None
    publish_date: Optional[str] = None
    state: Optional[str] = None
    image_url: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class SocialAutoPostCreate(BaseModel):
    title: str
    url: str
    active: bool = True
    generate_content: bool = False
    integrations: list[str] = []


class SocialTagCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class SocialWebhookSave(BaseModel):
    url: str
    active: bool = True


class SocialGenerateRequest(BaseModel):
    prompt: str
    tone: str = "professional"
    kind: str = "outlines"  # "outlines" | "post"
    url: Optional[str] = None
