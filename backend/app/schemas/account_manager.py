from typing import Optional

from pydantic import BaseModel


class AccountManagerAssign(BaseModel):
    user_id: str
    name: str
    email: str
    calendly_url: Optional[str] = None
