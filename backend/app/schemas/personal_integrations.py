from typing import Optional

from pydantic import BaseModel


class ExternalTaskToggleBody(BaseModel):
    completed: bool
    list_id: Optional[str] = None  # required for Microsoft ToDo


class GoogleContactBody(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None


class MicrosoftContactBody(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
