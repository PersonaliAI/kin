from typing import Optional

from pydantic import BaseModel


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    thinking: Optional[str] = None


class KinApiMessageRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
