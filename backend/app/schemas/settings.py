from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class KinApiKeyCreate(BaseModel):
    name: str = "API key"


class SignatureLink(BaseModel):
    label: Optional[str] = None
    url: str


class SettingsPatch(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None
    country: Optional[str] = None
    system_prompt: Optional[str] = None
    briefing_enabled: Optional[bool] = None
    briefing_time: Optional[str] = None  # "HH:MM:SS"
    marketing_opt_in: Optional[bool] = None
    memory_enabled: Optional[bool] = None
    confirm_before_write: Optional[bool] = None
    email_followups_enabled: Optional[bool] = None
    email_signature_enabled: Optional[bool] = None
    email_signature_name: Optional[str] = None
    email_signature_title: Optional[str] = None
    email_signature_phone: Optional[str] = None
    email_signature_links: Optional[list[SignatureLink]] = None


class FlowCredentialsSave(BaseModel):
    integration_slug: str
    payload: dict
