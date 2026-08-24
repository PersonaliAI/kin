from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class IntegrationPublish(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    manifest: Optional[Any] = None
    icon_url: Optional[str] = None
    publisher_name: Optional[str] = None
    openapi_url: Optional[str] = None


class ReviewSubmit(BaseModel):
    rating: int
    comment: Optional[str] = None


class OpenSkillVaultRequest(BaseModel):
    provider_slug: str
    end_user_id: str
