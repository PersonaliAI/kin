from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.clients import supabase
from app.core.deps import require_user
from app.schemas.marketplace import IntegrationPublish, OpenSkillVaultRequest, ReviewSubmit

from main import _decode_credentials_payload

logger = logging.getLogger("kin")

router = APIRouter()

# ---------------------------------------------------------------------------
# Flow & Integrations Directory Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/integrations-catalog")
async def get_integrations_catalog(category: Optional[str] = None, user: dict[str, Any] = Depends(require_user)):
    try:
        # Standard flow allows listing published integrations, or those created by this user
        query = supabase.table("integrations").select("*")
        if category:
            query = query.eq("category", category)

        # We show published integrations or those published by the current user
        query = query.or_(f"status.eq.published,publisher_user_id.eq.{user['id']}")

        res = query.execute()
        return {"integrations": res.data or []}
    except Exception as e:
        logger.exception("Failed to fetch integrations catalog")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integrations-catalog/{slug}")
async def get_integration(slug: str, user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("integrations").select("*").eq("slug", slug).maybe_single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Integration not found")
        return res.data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch integration")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integration-installs")
async def get_integration_installs(user: dict[str, Any] = Depends(require_user)):
    try:
        res = supabase.table("integration_installs").select("integration_slug, installed_at").eq("user_id", user["id"]).execute()
        return {"installs": res.data or []}
    except Exception as e:
        logger.exception("Failed to fetch integration installs")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/integration-installs/{slug}")
async def install_integration(slug: str, user: dict[str, Any] = Depends(require_user)):
    try:
        # Check if integration exists
        integ = supabase.table("integrations").select("slug").eq("slug", slug).maybe_single().execute()
        if not integ.data:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Upsert install
        supabase.table("integration_installs").upsert({
            "user_id": user["id"],
            "integration_slug": slug
        }).execute()

        # Increment install count
        try:
            supabase.rpc("increment_integration_install_count", {"integration_slug": slug}).execute()
        except Exception:
            # Fallback to direct update if RPC is missing
            try:
                curr = supabase.table("integrations").select("install_count").eq("slug", slug).maybe_single().execute()
                if curr.data:
                    new_count = (curr.data.get("install_count") or 0) + 1
                    supabase.table("integrations").update({"install_count": new_count}).eq("slug", slug).execute()
            except Exception:
                pass

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to install integration")
        return {"status": "success"}


@router.delete("/api/integration-installs/{slug}")
async def uninstall_integration(slug: str, user: dict[str, Any] = Depends(require_user)):
    try:
        supabase.table("integration_installs").delete().eq("user_id", user["id"]).eq("integration_slug", slug).execute()
        return {"status": "success"}
    except Exception as e:
        logger.exception("Failed to uninstall integration")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/integrations-catalog/{slug}/review")
async def review_integration(slug: str, body: ReviewSubmit, user: dict[str, Any] = Depends(require_user)):
    try:
        integ = supabase.table("integrations").select("id").eq("slug", slug).maybe_single().execute()
        if not integ.data:
            raise HTTPException(status_code=404, detail="Integration not found")

        supabase.table("integration_reviews").upsert({
            "integration_id": integ.data["id"],
            "user_id": user["id"],
            "rating": body.rating,
            "comment": body.comment
        }).execute()

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to submit review")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/integrations-publish")
async def publish_integration(body: IntegrationPublish, user: dict[str, Any] = Depends(require_user)):
    try:
        slug = body.slug or f"custom-{uuid.uuid4().hex[:8]}"
        name = body.name or "Custom Integration"
        description = body.description or ""
        category = body.category or "productivity"
        manifest = body.manifest or {}
        icon_url = body.icon_url or ""
        publisher_name = body.publisher_name or user.get("display_name") or "User"

        if body.openapi_url:
            async with httpx.AsyncClient() as client:
                resp = await client.get(body.openapi_url)
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail="Failed to fetch OpenAPI specification from URL.")
                spec_text = resp.text

            try:
                try:
                    spec = json.loads(spec_text)
                except Exception:
                    spec = yaml.safe_load(spec_text)

                info = spec.get("info", {})
                name = body.name or info.get("title", name)
                description = body.description or info.get("description", description)

                actions = []
                paths = spec.get("paths", {})
                for path, path_item in paths.items():
                    for method, operation in path_item.items():
                        if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                            continue

                        op_id = operation.get("operationId") or f"{method}_{path.replace('/', '_').strip('_')}"
                        summary = operation.get("summary") or operation.get("description") or f"{method.upper()} {path}"

                        inputs = []
                        parameters = operation.get("parameters", [])
                        parameters += path_item.get("parameters", [])

                        for param in parameters:
                            inputs.append({
                                "name": param.get("name"),
                                "in": param.get("in"),
                                "required": param.get("required", False),
                                "type": param.get("schema", {}).get("type", "string"),
                                "description": param.get("description", "")
                            })

                        request_body = operation.get("requestBody", {})
                        if request_body:
                            content = request_body.get("content", {})
                            json_content = content.get("application/json", {})
                            schema = json_content.get("schema", {})
                            if schema.get("type") == "object":
                                properties = schema.get("properties", {})
                                required_fields = schema.get("required", [])
                                for prop_name, prop_schema in properties.items():
                                    inputs.append({
                                        "name": prop_name,
                                        "in": "body",
                                        "required": prop_name in required_fields,
                                        "type": prop_schema.get("type", "string"),
                                        "description": prop_schema.get("description", "")
                                    })

                        actions.append({
                            "name": op_id,
                            "description": summary,
                            "path": path,
                            "method": method.upper(),
                            "inputs": inputs
                        })

                manifest = {
                    "auth": {
                        "type": "api_key",
                        "fields": [
                            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
                        ]
                    },
                    "actions": actions,
                    "triggers": []
                }
            except Exception as pe:
                logger.exception("OpenAPI parse failed")
                raise HTTPException(status_code=400, detail=f"Failed to parse OpenAPI spec: {str(pe)}")

        res = supabase.table("integrations").upsert({
            "slug": slug,
            "name": name,
            "description": description,
            "category": category,
            "manifest": manifest,
            "icon_url": icon_url,
            "publisher_user_id": user["id"],
            "publisher_name": publisher_name,
            "source": "community",
            "status": "published",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save published integration.")

        # Automatically install it for the publisher
        supabase.table("integration_installs").upsert({
            "user_id": user["id"],
            "integration_slug": slug
        }).execute()

        return {
            "status": "success",
            "slug": slug,
            "name": name,
            "description": description,
            "category": category,
            "publisher_name": publisher_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to publish integration")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/openskill/v1/vault/resolve")
async def openskill_vault_resolve(body: OpenSkillVaultRequest, request: Request):
    """
    OpenSkill Cloud API Gateway.
    Allows external OpenSkill developers to securely fetch credentials from the vault
    by providing their SaaS API Key (mocked here for MVP) and their end-user ID.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    # MVP: Mock verification of the developer's API Key
    developer_api_key = auth_header.split(" ")[1]
    if not developer_api_key.startswith("sk_live_"):
        raise HTTPException(status_code=403, detail="Invalid OpenSkill Developer API Key")

    try:
        # Fetch the requested credential from the end_user's vault
        res = supabase.table("user_credentials").select("encrypted_payload").eq("user_id", body.end_user_id).eq("integration_slug", body.provider_slug).maybe_single().execute()

        if not res.data or not res.data.get("encrypted_payload"):
            raise HTTPException(status_code=404, detail=f"No credential found for provider '{body.provider_slug}'")

        payload = _decode_credentials_payload(res.data["encrypted_payload"])
        return {"credentials": payload}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to resolve OpenSkill credentials")
        raise HTTPException(status_code=500, detail=str(e))
