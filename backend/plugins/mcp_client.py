import asyncio
import json
import logging
import urllib.parse
from typing import Any, Dict, Optional, List, Protocol
import httpx

logger = logging.getLogger("kin.mcp")

MCP_PROTOCOL_VERSION = "2025-03-26"
CLIENT_INFO = {"name": "Kin Personal AI", "version": "1.0.0"}


class _RemoteMCPClient(Protocol):
    """Shape both transport implementations satisfy, so callers don't
    need to know which one they actually got."""

    async def connect(self) -> None: ...
    async def list_tools(self) -> List[Dict[str, Any]]: ...
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]: ...
    async def close(self) -> None: ...


class StreamableHTTPClient:
    """MCP Streamable HTTP transport (spec 2025-03-26) — a single endpoint;
    POST a JSON-RPC request, get back either a plain JSON response or a
    short-lived SSE stream containing exactly one JSON-RPC response.

    This is the transport most MCP servers built after March 2025 default
    to (the official SDKs' `streamable-http` mode). The legacy `SSEClient`
    below only understands the older two-endpoint SSE transport, so
    servers that dropped it in favor of this one would previously hang
    for 10s and fail to connect at all.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = dict(headers or {})
        self.session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        init_result = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
            capture_session=True,
        )
        if "error" in init_result:
            raise RuntimeError(f"MCP initialize failed: {init_result['error']}")
        # Notification — no response expected, best-effort.
        await self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )

    def _request_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    async def _post(self, payload: Dict[str, Any]) -> httpx.Response:
        assert self._client is not None
        return await self._client.post(self.url, json=payload, headers=self._request_headers())

    async def _request(
        self, method: str, params: Dict[str, Any], capture_session: bool = False
    ) -> Dict[str, Any]:
        req_id = str(asyncio.get_event_loop().time())
        res = await self._post(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}
        )
        if capture_session:
            sid = res.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
        res.raise_for_status()
        content_type = res.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._extract_sse_response(res.text, req_id)
        return res.json()

    @staticmethod
    def _extract_sse_response(text: str, req_id: str) -> Dict[str, Any]:
        """The POST response body is itself SSE-framed — parse out the one
        JSON-RPC message matching our request id."""
        current_data: List[str] = []
        for raw_line in text.splitlines() + [""]:
            line = raw_line.strip()
            if line.startswith("data:"):
                current_data.append(line[len("data:"):].strip())
                continue
            if line:
                continue
            if not current_data:
                continue
            try:
                msg = json.loads("\n".join(current_data))
                if str(msg.get("id")) == req_id:
                    return msg
            except Exception:  # noqa: BLE001
                pass
            current_data = []
        return {"error": {"message": "No matching response in SSE stream"}}

    async def list_tools(self) -> List[Dict[str, Any]]:
        response = await self._request("tools/list", {})
        result = response.get("result", {})
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        response = await self._request("tools/call", {"name": tool_name, "arguments": arguments})
        if "error" in response:
            return {"error": response["error"]}
        return response.get("result", {})

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


class SSEClient:
    """Legacy MCP HTTP+SSE transport (pre 2025-03-26 spec) — a GET stream
    that announces a separate POST endpoint via an `event: endpoint`
    message, kept for servers that never upgraded to Streamable HTTP."""

    def __init__(self, sse_url: str, headers: Optional[Dict[str, str]] = None):
        self.sse_url = sse_url
        self.headers = headers or {}
        self.post_url: Optional[str] = None
        self._endpoint_future = asyncio.Future()
        self._responses: Dict[str, asyncio.Future] = {}
        self._stream_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self):
        # Merge headers with common accept/connection headers if needed
        req_headers = {
            "Accept": "text/event-stream",
            **self.headers
        }
        self._client = httpx.AsyncClient(timeout=30.0)
        self._stream_task = asyncio.create_task(self._read_stream(req_headers))
        # Wait for the endpoint event
        self.post_url = await asyncio.wait_for(self._endpoint_future, timeout=10.0)
        logger.info(f"Connected to MCP SSE server at {self.sse_url}. POST endpoint is {self.post_url}")

    async def _read_stream(self, headers: Dict[str, str]):
        try:
            async with self._client.stream("GET", self.sse_url, headers=headers) as response:
                response.raise_for_status()
                current_event = None
                current_data: List[str] = []
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        # Empty line acts as event boundary
                        if current_event and current_data:
                            data_str = "\n".join(current_data)
                            await self._handle_event(current_event, data_str)
                        current_event = None
                        current_data = []
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        current_data.append(line[len("data:"):].strip())
                
                # Handle trailing event if connection closes without empty line
                if current_event and current_data:
                    data_str = "\n".join(current_data)
                    await self._handle_event(current_event, data_str)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Error in SSE stream reader")
            if not self._endpoint_future.done():
                self._endpoint_future.set_exception(e)
            for fut in self._responses.values():
                if not fut.done():
                    fut.set_exception(e)

    async def _handle_event(self, event: str, data: str):
        if event == "endpoint":
            # The server sends a URI (relative or absolute) for POST messages
            resolved_url = urllib.parse.urljoin(self.sse_url, data)
            if not self._endpoint_future.done():
                self._endpoint_future.set_result(resolved_url)
        elif event == "message":
            try:
                msg = json.loads(data)
                msg_id = str(msg.get("id")) if msg.get("id") is not None else None
                if msg_id and msg_id in self._responses:
                    if not self._responses[msg_id].done():
                        self._responses[msg_id].set_result(msg)
            except Exception:
                logger.exception("Failed to parse message JSON: %s", data)

    async def call_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.post_url:
            raise RuntimeError("Client not connected or endpoint not received")
        
        req_id = str(asyncio.get_event_loop().time())
        request_payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id
        }
        
        response_future = asyncio.Future()
        self._responses[req_id] = response_future
        
        try:
            # Send POST message
            res = await self._client.post(self.post_url, json=request_payload, headers=self.headers)
            res.raise_for_status()
            
            # Check if server responded immediately in the POST response (optional fallback)
            try:
                body = res.json()
                if isinstance(body, dict) and str(body.get("id")) == req_id:
                    return body
            except Exception:
                pass
            
            # Wait for response on SSE stream
            response_data = await asyncio.wait_for(response_future, timeout=20.0)
            return response_data
        finally:
            self._responses.pop(req_id, None)

    async def list_tools(self) -> List[Dict[str, Any]]:
        response = await self.call_method("tools/list", {})
        result = response.get("result", {})
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.call_method("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if "error" in response:
            return {"error": response["error"]}
        return response.get("result", {})

    async def close(self):
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()


async def _connect_any(url: str, headers: Optional[Dict[str, str]] = None) -> _RemoteMCPClient:
    """Connect to an MCP server regardless of which transport it speaks.

    Per the spec's documented backward-compatibility strategy: try
    Streamable HTTP first (POST straight to the given URL). If the server
    doesn't understand that — 404/405, or it never replies with a valid
    JSON-RPC response — fall back to the legacy two-endpoint SSE
    transport. Whichever succeeds is returned; the other is never touched
    again for this call.
    """
    http_client = StreamableHTTPClient(url, headers)
    try:
        await http_client.connect()
        return http_client
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "Streamable HTTP connect failed for %s (%s) — falling back to legacy SSE",
            url, exc,
        )
        await http_client.close()

    sse_client = SSEClient(url, headers)
    await sse_client.connect()
    return sse_client


async def list_remote_tools(sse_url: str, headers: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    client = await _connect_any(sse_url, headers)
    try:
        return await client.list_tools()
    finally:
        await client.close()


async def call_remote_tool(sse_url: str, tool_name: str, arguments: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    client = await _connect_any(sse_url, headers)
    try:
        return await client.call_tool(tool_name, arguments)
    finally:
        await client.close()


async def discover_mcp_oauth(sse_url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """Try to discover OAuth endpoints of an MCP server using RFC 9728 / WWW-Authenticate."""
    headers = headers or {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(sse_url, headers=headers)
            if res.status_code == 401:
                auth_header = res.headers.get("WWW-Authenticate") or ""
                import re
                
                # Check for standard RFC 9728 resource_metadata parameter
                metadata_match = re.search(r'resource_metadata=["\']([^"\']+)["\']', auth_header, re.IGNORECASE)
                if metadata_match:
                    metadata_url = metadata_match.group(1)
                    logger.info(f"Discovered resource metadata URL: {metadata_url}")
                    meta_res = await client.get(metadata_url)
                    if meta_res.status_code == 200:
                        meta_data = meta_res.json()
                        auth_servers = meta_data.get("authorization_servers", [])
                        for server_url in auth_servers:
                            if not server_url.endswith("/"):
                                server_url += "/"
                            # Check RFC 8414 OAuth authorization server metadata endpoints
                            for path in [".well-known/oauth-authorization-server", ".well-known/openid-configuration"]:
                                try:
                                    auth_meta_url = urllib.parse.urljoin(server_url, path)
                                    auth_res = await client.get(auth_meta_url)
                                    if auth_res.status_code == 200:
                                        auth_meta = auth_res.json()
                                        auth_ep = auth_meta.get("authorization_endpoint")
                                        token_ep = auth_meta.get("token_endpoint")
                                        reg_ep = auth_meta.get("registration_endpoint")
                                        if auth_ep and token_ep:
                                            return {
                                                "authorization_endpoint": auth_ep,
                                                "token_endpoint": token_ep,
                                                "registration_endpoint": reg_ep
                                            }
                                except Exception:
                                    pass

                # Fallback to direct WWW-Authenticate header parsing (authorization_uri / token_uri)
                auth_uri_match = re.search(r'authorization_uri=["\']([^"\']+)["\']', auth_header)
                token_uri_match = re.search(r'token_uri=["\']([^"\']+)["\']', auth_header)
                if auth_uri_match and token_uri_match:
                    return {
                        "authorization_endpoint": auth_uri_match.group(1),
                        "token_endpoint": token_uri_match.group(1)
                    }
                    
                # Legacy metadata_match check
                metadata_match_legacy = re.search(r'rel=["\']oauth2-helper["\']\s*,\s*href=["\']([^"\']+)["\']', auth_header) or re.search(r'oauth2-metadata=["\']([^"\']+)["\']', auth_header)
                if metadata_match_legacy:
                    meta_url = metadata_match_legacy.group(1)
                    meta_res = await client.get(meta_url)
                    if meta_res.status_code == 200:
                        meta_data = meta_res.json()
                        return {
                            "authorization_endpoint": meta_data.get("authorization_endpoint"),
                            "token_endpoint": meta_data.get("token_endpoint")
                        }
    except Exception:
        logger.exception("Failed to discover MCP OAuth metadata")
    return None


async def register_mcp_oauth_client(registration_url: str, redirect_uri: str) -> Optional[Dict[str, str]]:
    """Register Kin as a client dynamically with an MCP authorization server using RFC 7591."""
    try:
        payload = {
            "client_name": "Kin Personal AI",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(registration_url, json=payload)
            if res.status_code in (200, 201):
                data = res.json()
                if "client_id" in data:
                    return {
                        "client_id": data["client_id"],
                        "client_secret": data.get("client_secret")
                    }
            logger.error(f"Failed to register MCP OAuth client dynamically: Status {res.status_code}, Body {res.text}")
    except Exception:
        logger.exception("Error registering MCP OAuth client")
    return None



async def refresh_mcp_oauth_token(server_id: str) -> Optional[str]:
    """Check and refresh the OAuth token for an MCP server if needed.
    Returns the valid access token, or None if not authorized.
    """
    from supabase import create_client
    import os
    from datetime import datetime, timezone, timedelta
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logger.error("Supabase environment variables not set")
        return None
        
    try:
        supabase = create_client(url, key)
        res = supabase.table("mcp_servers").select("*").eq("id", server_id).execute()
        if not res.data:
            return None
        server = res.data[0]
    except Exception:
        logger.exception("Failed to query MCP server for token refresh")
        return None
        
    access_token = server.get("oauth_access_token")
    if not access_token:
        return None
        
    expires_at_str = server.get("oauth_token_expires_at")
    refresh_token = server.get("oauth_refresh_token")
    token_url = server.get("oauth_token_url")
    
    is_expired = False
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at - timedelta(seconds=60):
                is_expired = True
        except Exception:
            is_expired = True
            
    if is_expired and refresh_token and token_url:
        logger.info("MCP server OAuth token is expired or close to expiry. Refreshing...")
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": server.get("oauth_client_id"),
            }
            client_secret = server.get("oauth_client_secret")
            if client_secret:
                payload["client_secret"] = client_secret
                
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(token_url, data=payload)
                if res.status_code == 200:
                    tokens = res.json()
                    new_access = tokens["access_token"]
                    new_refresh = tokens.get("refresh_token") or refresh_token
                    expires_in = int(tokens.get("expires_in", 3600))
                    
                    update_data = {
                        "oauth_access_token": new_access,
                        "oauth_refresh_token": new_refresh,
                        "oauth_token_expires_at": (
                            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                        ).isoformat(),
                        "oauth_flow_status": "authorized"
                    }
                    supabase.table("mcp_servers").update(update_data).eq("id", server_id).execute()
                    return new_access
                else:
                    logger.error(
                        "Failed to refresh MCP OAuth token: Status %d, Body %s",
                        res.status_code, res.text
                    )
        except Exception:
            logger.exception("Failed to refresh MCP OAuth token")
            
    return access_token


async def get_mcp_headers(server: dict) -> dict:
    """Prepares and merges headers, including refreshing OAuth tokens if configured."""
    import json
    headers = server.get("headers") or {}
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except Exception:
            headers = {}
            
    if server.get("oauth_flow_status") == "authorized" or server.get("oauth_access_token"):
        token = await refresh_mcp_oauth_token(server["id"])
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
    return headers

