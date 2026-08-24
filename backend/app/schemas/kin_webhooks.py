from typing import Optional

from pydantic import BaseModel


class KinWebhookCreate(BaseModel):
    url: str
    events: list[str] = ["message.created"]


class KinWebhookPatch(BaseModel):
    active: Optional[bool] = None
