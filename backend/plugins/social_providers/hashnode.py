"""Hashnode — Personal Access Token + GraphQL API (no OAuth). Token generated
at https://hashnode.com/settings/developer; publication id is the target
blog to publish to (from https://hashnode.com/{username}/dashboard).
"""

from __future__ import annotations

from typing import Any, Optional

from .base import SocialPostError, SocialProvider, request_with_retry

API_URL = "https://gql.hashnode.com/"


async def _gql(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    res = await request_with_retry(
        "POST", API_URL,
        headers={"Authorization": token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables},
    )
    if res.status_code >= 400:
        raise SocialPostError(f"hashnode request failed ({res.status_code}): {res.text}")
    data = res.json()
    if data.get("errors"):
        raise SocialPostError(f"hashnode error: {data['errors']}")
    return data["data"]


class HashnodeProvider(SocialProvider):
    identifier = "hashnode"
    name = "Hashnode"
    oauth2 = False

    async def connect_manual(self, form: dict[str, Any]) -> dict[str, Any]:
        token = (form.get("api_key") or "").strip()
        publication_id = (form.get("publication_id") or "").strip()
        if not token or not publication_id:
            raise SocialPostError("Enter your Hashnode API token and publication id")
        data = await _gql(token, "query { me { id username } }", {})
        return {"api_key": token, "publication_id": publication_id, "username": data.get("me", {}).get("username")}

    async def post(
        self,
        content: str,
        credentials: dict[str, Any],
        media_urls: Optional[list[str]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        title, _, body = content.partition("\n")
        title = title[:250] or "New post"
        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) { post { id url } }
        }
        """
        variables = {
            "input": {
                "title": title,
                "publicationId": credentials["publication_id"],
                "contentMarkdown": body or content,
                **({"coverImageOptions": {"coverImageURL": media_urls[0]}} if media_urls else {}),
            }
        }
        data = await _gql(credentials["api_key"], mutation, variables)
        post = data.get("publishPost", {}).get("post", {})
        return {"status": "posted", "postId": post.get("id", ""), "releaseURL": post.get("url", "")}

    async def fetch_analytics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        if not post_id:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        query = "query Post($id: ID!) { post(id: $id) { views reactionCount responseCount } }"
        try:
            data = await _gql(credentials["api_key"], query, {"id": post_id})
        except SocialPostError:
            return {"impressions": 0, "likes": 0, "reposts": 0, "comments": 0, "clicks": 0}
        post = data.get("post") or {}
        return {
            "impressions": post.get("views", 0),
            "likes": post.get("reactionCount", 0),
            "reposts": 0,
            "comments": post.get("responseCount", 0),
            "clicks": 0,
        }
