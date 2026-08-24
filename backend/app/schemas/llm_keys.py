from __future__ import annotations

from pydantic import BaseModel


class LlmKeySave(BaseModel):
    provider: str
    api_key: str
