"""Placeholder provider used for the 24+ platforms not yet ported to a real
implementation (see the batch order in the integration plan). Keeps existing
DB rows / frontend platform list working while real providers are built out
one batch at a time — swap an entry in registry.PROVIDERS to upgrade a slug.
"""

import os
import logging
from typing import Any, Optional

from .base import SocialProvider

logger = logging.getLogger("kin.social")


class GenericSocialProvider(SocialProvider):
    oauth2 = False

    def __init__(self, provider_id: str, provider_name: str):
        self._id = provider_id
        self._name = provider_name

    @property
    def identifier(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    async def post(self, content: str, credentials: dict, media_urls: Optional[list[str]] = None, settings: Optional[dict] = None) -> dict:
        logger.warning("%s has no real provider yet — simulating post", self.name)
        post_id = f"post_{self.identifier}_" + os.urandom(4).hex()
        return {
            "status": "posted",
            "postId": post_id,
            "releaseURL": f"https://{self.identifier}.com/posts/{post_id}",
        }

    async def comment(self, post_id: str, content: str, credentials: dict) -> dict:
        comment_id = f"comment_{self.identifier}_" + os.urandom(4).hex()
        return {
            "status": "posted",
            "postId": comment_id,
            "releaseURL": f"https://{self.identifier}.com/posts/{post_id}?comment={comment_id}",
        }

    async def fetch_analytics(self, post_id: str, credentials: dict) -> dict:
        return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
