"""kin-voice-worker — the single LiveKit Agents worker process that serves
every Kin voice agent (sales / receptionist phone agents), for every tenant.

There is exactly ONE registered entrypoint (`entrypoint` below). Which
persona/LLM/STT/TTS/tools a given call actually uses is decided at runtime
from `ctx.job.metadata`, which kin-backend sets to a small JSON blob
containing a `voice_agent_id` when it dispatches a call (see
kin-backend/livekit_control.py for outbound dialing, and the LiveKit SIP
inbound-dispatch-rule config for inbound calls — both point at this same
worker via LIVEKIT_AGENT_NAME).

Run modes (see AGENTS.md in the vendored livekit/agents repo):
    python worker.py console   # local mic/speaker test, no telephony needed
    python worker.py dev       # connects to LiveKit, hot reload
    python worker.py start     # production (what the Dockerfile CMDs)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
)
from livekit.agents.llm import function_tool

# Plugin registration must happen on the main thread at process startup —
# LiveKit raises "Plugins must be registered on the main thread" if a
# plugin module is first imported later, inside a per-job handler running
# in a job subprocess/thread. Hence importing every plugin up front here,
# matching requirements.txt exactly, instead of lazily inside build_llm/
# build_stt/build_tts (confirmed against a real dispatched job locally).
from livekit.plugins import (
    anthropic,
    assemblyai,
    azure,
    cartesia,
    deepgram,
    elevenlabs,
    google,
    lmnt,
    openai,
    rime,
    xai,
)

load_dotenv()

logger = logging.getLogger("kin-voice-worker")

KIN_BACKEND_URL = os.environ["KIN_BACKEND_URL"].rstrip("/")
FUNCTION_SECRET = os.environ.get("FUNCTION_SECRET", "")

DEFAULT_GREETING_INSTRUCTION = "Greet the caller and briefly introduce yourself, then let them talk."

# Enabled tools are looked up by name against this catalogue — the JSON
# schema mirrors the corresponding FunctionDeclaration in kin-backend's
# agent_tools.py so the LLM sees the exact same tool shape on a phone call
# as it does in chat. Execution is delegated to kin-backend
# (POST /internal/voice-tools/execute), which reuses agent_tools.execute()
# directly rather than reimplementing calendar/CRM logic here.
AVAILABLE_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "create_calendar_event": {
        "name": "create_calendar_event",
        "description": "Book a calendar event/meeting for the caller.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string", "description": "ISO 8601 start time."},
                "end_time": {"type": "string", "description": "ISO 8601 end time."},
                "attendee_email": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["title", "start_time", "end_time"],
        },
    },
    "check_calendar_availability": {
        "name": "check_calendar_availability",
        "description": "Check whether a given time range is free on the calendar.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
            },
            "required": ["start_time", "end_time"],
        },
    },
    "create_lead": {
        "name": "create_lead",
        "description": "Record the caller's contact details as a sales lead.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    # Mirrors agent_tools.py's Gemini FunctionDeclaration of the same name
    # (chat's RAG search tool) as a plain JSON schema — this is what gives a
    # voice call the same knowledge-base grounding chat has, instead of only
    # the agent's static persona text. Executed the same way every other
    # voice tool is: kin-backend's /internal/voice-tools/execute dispatches
    # straight to agent_tools.execute(), so behavior (including the
    # keyword-search fallback when vector search returns nothing) is
    # identical to chat, not reimplemented here.
    "search_documents": {
        "name": "search_documents",
        "description": (
            "Semantic search across the caller's indexed documents (Drive, OneDrive, and "
            "anything uploaded through chat) for a SPECIFIC fact, figure, policy, or clause "
            "a file might answer. Returns the most relevant text chunks with source filenames — "
            "cite them in your reply. For 'summarize this file' style requests, use "
            "read_full_document instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language question to search for."},
                "limit": {"type": "integer", "description": "Max chunks to return (default 8, max 15)."},
            },
            "required": ["query"],
        },
    },
    "read_full_document": {
        "name": "read_full_document",
        "description": (
            "Fetch the COMPLETE indexed text of ONE document by filename — use this on the "
            "first attempt for 'summarize this', 'what does this say overall' style requests, "
            "instead of retrying search_documents with rephrased queries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Filename or partial filename."},
            },
            "required": ["file_name"],
        },
    },
}


def _backend_client() -> httpx.AsyncClient:
    # Sent as a header rather than a query param so it never lands in
    # Cloud Run request logs or proxy logs in plaintext (kin-backend's
    # /internal/* routes accept this header; the query param is still
    # accepted there too, for callers that can't easily be changed).
    return httpx.AsyncClient(
        base_url=KIN_BACKEND_URL,
        timeout=20.0,
        headers={"Authorization": f"Bearer {FUNCTION_SECRET}"},
    )


async def fetch_voice_agent_config(voice_agent_id: str) -> dict[str, Any]:
    async with _backend_client() as client:
        resp = await client.get(f"/internal/voice-agents/{voice_agent_id}/config")
        resp.raise_for_status()
        return resp.json()


async def report_call_event(**fields: Any) -> dict[str, Any]:
    async with _backend_client() as client:
        resp = await client.post(
            "/internal/voice-calls",
            json={k: v for k, v in fields.items() if v is not None},
        )
        resp.raise_for_status()
        return resp.json()


async def execute_backend_tool(voice_agent_id: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    async with _backend_client() as client:
        resp = await client.post(
            "/internal/voice-tools/execute",
            json={"voice_agent_id": voice_agent_id, "tool_name": tool_name, "args": args},
        )
        resp.raise_for_status()
        return resp.json()


def _split_azure_key(raw: str) -> tuple[str, str]:
    """Azure Speech needs a key AND a region, not just a key — the
    dashboard's single BYOK field encodes both as "region:key" (see
    voice-agents-view.tsx's Azure-specific hint text)."""
    region, _, key = raw.partition(":")
    if not key:
        raise ValueError("Azure key must be entered as 'region:key' (e.g. 'eastus:abcd1234...')")
    return region, key


def build_llm(provider: str, model: str, api_key: Optional[str]):
    # BYOK — every branch is passed the voice agent owner's own key
    # (decrypted server-side by kin-backend, never a platform-wide key).
    if provider == "openai":
        return openai.LLM(model=model, api_key=api_key)
    if provider == "anthropic":
        return anthropic.LLM(model=model, api_key=api_key)
    if provider == "google":
        return google.LLM(model=model, api_key=api_key)
    if provider == "xai":
        return xai.responses.LLM(model=model, api_key=api_key)
    raise ValueError(f"Unsupported llm_provider: {provider}")


def build_stt(provider: str, api_key: Optional[str]):
    if provider == "deepgram":
        return deepgram.STT(api_key=api_key)
    if provider == "google":
        # No simple API key — the plugin expects a GCP service-account.
        # The BYOK field holds the service-account JSON itself (pasted
        # whole), not a short key string.
        if not api_key:
            raise ValueError("Google STT requires a service-account JSON credential")
        return google.STT(credentials_info=json.loads(api_key))
    if provider == "azure":
        region, key = _split_azure_key(api_key or "")
        return azure.STT(speech_key=key, speech_region=region)
    if provider == "assemblyai":
        return assemblyai.STT(api_key=api_key)
    if provider == "openai":
        return openai.STT(api_key=api_key)
    raise ValueError(f"Unsupported stt_provider: {provider}")


def build_tts(provider: str, voice: Optional[str], api_key: Optional[str]):
    if provider == "elevenlabs":
        return elevenlabs.TTS(api_key=api_key, **({"voice_id": voice} if voice else {}))
    if provider == "cartesia":
        return cartesia.TTS(api_key=api_key, **({"voice": voice} if voice else {}))
    if provider == "rime":
        return rime.TTS(api_key=api_key, **({"speaker": voice} if voice else {}))
    if provider == "lmnt":
        return lmnt.TTS(api_key=api_key, **({"voice": voice} if voice else {}))
    if provider == "azure":
        region, key = _split_azure_key(api_key or "")
        return azure.TTS(speech_key=key, speech_region=region, **({"voice": voice} if voice else {}))
    if provider == "google":
        # Same as Google STT — no simple API key, the BYOK field holds a
        # pasted service-account JSON credential.
        if not api_key:
            raise ValueError("Google TTS requires a service-account JSON credential")
        return google.TTS(credentials_info=json.loads(api_key), **({"voice_name": voice} if voice else {}))
    raise ValueError(f"Unsupported tts_provider: {provider}")


def build_realtime(provider: str, model: str, voice: Optional[str], api_key: Optional[str]):
    """Speech-to-speech models (audio in, audio out) — used instead of
    build_stt/build_llm/build_tts entirely when a voice agent's mode is
    "realtime" (see kin-backend's VOICE_AGENT_REALTIME_PROVIDERS). Passed as
    AgentSession(llm=...) same as a regular LLM — LiveKit's AgentSession
    accepts either interchangeably."""
    if provider == "google":
        kwargs: dict[str, Any] = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        if voice:
            kwargs["voice"] = voice
        return google.realtime.RealtimeModel(**kwargs)
    if provider == "openai":
        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        if voice:
            kwargs["voice"] = voice
        return openai.realtime.RealtimeModel(**kwargs)
    raise ValueError(f"Unsupported realtime provider: {provider}")


def build_tools(voice_agent_id: str, enabled_tool_names: list[str]) -> list:
    tools = []
    for tool_name in enabled_tool_names:
        schema = AVAILABLE_TOOL_SCHEMAS.get(tool_name)
        if not schema:
            logger.warning("Voice agent %s has unknown tool %r enabled, skipping", voice_agent_id, tool_name)
            continue

        async def _run(
            raw_arguments: dict[str, Any],
            context: RunContext,
            _name: str = tool_name,
            _schema: dict[str, Any] = schema,
        ) -> Any:
            missing = [
                field
                for field in _schema.get("parameters", {}).get("required", [])
                if field not in raw_arguments
            ]
            if missing:
                return {"error": f"missing required argument(s): {', '.join(missing)}"}
            return await execute_backend_tool(voice_agent_id, _name, raw_arguments)

        tools.append(function_tool(_run, raw_schema=schema))
    return tools


class KinVoiceAgent(Agent):
    def __init__(self, config: dict[str, Any]) -> None:
        instructions = config["persona"]
        super().__init__(
            instructions=instructions,
            tools=build_tools(config["id"], config.get("tools") or []),
        )
        self._greeting = config.get("greeting")

    async def on_enter(self) -> None:
        if self._greeting:
            self.session.say(self._greeting)
        else:
            self.session.generate_reply(instructions=DEFAULT_GREETING_INSTRUCTION)


# Cloud Run only considers the container healthy once something listens on
# $PORT — AgentServer's built-in health-check HTTP server (used for k8s
# liveness probes) covers that for free as long as we point it at $PORT
# instead of its own default (8081 in prod mode).
server = AgentServer(port=int(os.environ.get("PORT", 8081)))


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    metadata: dict[str, Any] = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
        except ValueError:
            logger.error("Job metadata was not valid JSON: %r", ctx.job.metadata)

    voice_agent_id = metadata.get("voice_agent_id")
    if not voice_agent_id:
        logger.error("Job has no voice_agent_id in metadata — cannot serve this call")
        return

    ctx.log_context_fields = {"room": ctx.room.name, "voice_agent_id": voice_agent_id}

    config = await fetch_voice_agent_config(voice_agent_id)

    call_log = await report_call_event(
        voice_agent_id=voice_agent_id,
        direction=metadata.get("direction", "inbound"),
        from_number=metadata.get("from_number"),
        to_number=metadata.get("to_number"),
    )
    call_id = call_log["id"]

    if config.get("mode") == "realtime":
        # Speech-to-speech — no separate STT/TTS stage, so those config
        # fields (and their BYOK keys) are unused here.
        session: AgentSession = AgentSession(
            llm=build_realtime(
                config["llm_provider"], config["llm_model"], config.get("tts_voice"), config.get("llm_api_key")
            ),
        )
    else:
        session = AgentSession(
            stt=build_stt(config["stt_provider"], config.get("stt_api_key")),
            llm=build_llm(config["llm_provider"], config["llm_model"], config.get("llm_api_key")),
            tts=build_tts(config["tts_provider"], config.get("tts_voice"), config.get("tts_api_key")),
        )

    transcript: list[dict[str, Any]] = []

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:  # noqa: ANN001 — event type varies by SDK version
        item = getattr(ev, "item", None)
        if item is not None:
            transcript.append({"role": getattr(item, "role", "?"), "text": getattr(item, "text_content", "")})

    async def _on_shutdown() -> None:
        await report_call_event(
            voice_agent_id=voice_agent_id,
            call_id=call_id,
            transcript=transcript,
            ended=True,
        )

    ctx.add_shutdown_callback(_on_shutdown)

    await session.start(agent=KinVoiceAgent(config), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
