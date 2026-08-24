from typing import Optional

from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    name: str
    prompt: str
    cron_expression: str
    timezone: str = "UTC"
    channel: str = "web"


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    channel: Optional[str] = None
    is_active: Optional[bool] = None
