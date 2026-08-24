from typing import Optional

from pydantic import BaseModel


class McpCreate(BaseModel):
    name: str
    url: str
    headers: Optional[dict] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_auth_url: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_scopes: Optional[str] = None
