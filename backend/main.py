"""PersonaliAI / Kin backend.

A single FastAPI service that:
  * Accepts Telegram updates (text or voice) at /webhook/telegram
  * Accepts web-app chat requests at /api/chat (multipart: text + optional audio)
  * Routes both through the same Gemma 4 multimodal runner
  * Persists every turn to Supabase (messages table)
  * Owns Google OAuth (Calendar + Gmail read scopes) + exposes endpoints the
    dashboard uses to read events/inbox
  * Handles Lemon Squeezy webhooks (HMAC verified, idempotent) and Telegram linking
  * Runs the daily morning briefing cron
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncio
import httpx
import jwt
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse, StreamingResponse, PlainTextResponse, Response
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

from plugins import agent_tools
from plugins import doc_rag
from plugins import graph_agent
from plugins import google_integrations as g
from plugins import livekit_control
from plugins import llm_providers
from plugins import memory as mem
from plugins import microsoft_integrations as ms
from plugins import notifications as notify
from plugins import telephony_providers

from app.core import security as _sec
from app.core.app_factory import create_app
from app.core.clients import genai_client, supabase
from app.core.config import (
    ALLOWED_ORIGINS,
    FRONTEND_URL,
    FUNCTION_SECRET,
    MODEL_NAME,
    OAUTH_STATE_SECRET,
)
from app.core.deps import get_user_by_auth_id, require_user, verify_supabase_jwt
from app.core.llm import complete as llm_complete
from app.core import gemini_compat

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kin")

DEFAULT_SYSTEM_PROMPT = (
    "You are Kin, a calm and capable personal assistant.\n"
    "Today's date is {today}.\n\n"
    "TOOLS:\n"
    "Gmail (READ): read_gmail (search/list), get_gmail_message (full body).\n"
    "Gmail (WRITE): send_email, reply_email, draft_email, modify_email_labels "
    "(mark read/unread, archive, custom labels), trash_email, list_gmail_labels.\n"
    "Calendar: read_calendar, get_calendar_event, create_calendar_event, "
    "update_calendar_event, delete_calendar_event, check_calendar_availability "
    "(free/busy).\n"
    "Google Tasks: list_google_task_lists, list_google_tasks, create_google_task, "
    "update_google_task (incl. marking completed), delete_google_task.\n"
    "Google Contacts: list_google_contacts (search), get_google_contact, "
    "create_google_contact, update_google_contact.\n"
    "Drive / Docs / Sheets / Slides: search_documents (RAG semantic search across "
    "indexed Drive AND OneDrive files — use this FIRST for any factual/policy/"
    "document question), list_drive_files (live Drive search by name), "
    "read_google_doc, read_google_sheet, list_sheet_tabs, read_google_slides, "
    "get_spreadsheet_info (sheet names/count for uploaded .xlsx/.xls files).\n"
    "Microsoft 365 (separate from Google):\n"
    "  • Outlook mail: read_outlook, get_outlook_message, send_outlook_email, "
    "reply_outlook_email, mark_outlook_read, delete_outlook_message, "
    "move_outlook_message, list_outlook_folders, create_outlook_folder, "
    "list_outlook_folder_messages.\n"
    "  • Outlook drafts: create_outlook_draft, update_outlook_draft, "
    "send_outlook_draft, update_outlook_message.\n"
    "  • Outlook calendar: list_outlook_calendars, list_outlook_events, "
    "get_outlook_event, create_outlook_event, update_outlook_event, "
    "delete_outlook_event.\n"
    "  • Outlook contacts: list_outlook_contacts, get_outlook_contact, "
    "create_outlook_contact, delete_outlook_contact.\n"
    "  • OneDrive: list_onedrive_files, get_onedrive_metadata, "
    "upload_onedrive_text_file, create_onedrive_folder, rename_onedrive_item, "
    "move_onedrive_item, copy_onedrive_item, delete_onedrive_item, "
    "share_onedrive_item.\n"
    "  • Microsoft ToDo: list_todo_lists, create_todo_list, list_todo_tasks, "
    "create_todo_task, update_todo_task, delete_todo_task.\n"
    "If user asks about 'outlook' or 'microsoft mail', use the outlook tools, "
    "NOT gmail. If user asks about Outlook calendar / Microsoft calendar, use "
    "the outlook calendar tools, NOT Google Calendar. If they say just 'tasks', "
    "ask which (Kin-local / Google / Microsoft ToDo).\n"
    "Kin-local (NOT Google): read_tasks, read_contacts — the user's dashboard "
    "tasks/contacts inside Kin.\n"
    "Memory: recall_memory — vector search of long-term notes.\n\n"
    "RULES:\n"
    "1. NEVER say 'I cannot access your data' or 'I can't directly access' — you HAVE the tools. "
    "Always call the right tool before refusing. If a file is not indexed, offer to help the "
    "user index it via /dashboard/documents.\n"
    "2. WRITE OPS (send_email, create/update/delete events, tasks, contacts) "
    "have real-world side effects. ALWAYS confirm with the user before calling "
    "if there is any ambiguity about who to send to / what time to schedule / "
    "what content to write. Quote back the exact recipient + subject + body / "
    "event details and ask 'shall I send/schedule this?' if you're not 100% sure.\n"
    "3. If a tool returns 'Google not connected' or 'Microsoft not connected', "
    "tell the user to visit /dashboard/integrations.\n"
    "4. Be helpful, proactive, and comprehensive. Give concrete answers with "
    "dates, times, and sender names. When the user asks for a summary, daily "
    "briefing, or information — just DO IT immediately by calling the appropriate "
    "tools. Do NOT ask for permission or confirmation when the user is requesting "
    "information (only confirm before WRITE operations).\n"
    "5. For 'tasks' or 'contacts' without context, ASK which the user means — "
    "Kin-local or Google. Do NOT silently pick one.\n"
    "6. For times in create/update_calendar_event, use ISO 8601 in the user's "
    "local timezone (not UTC).\n"
    "7. For 'what did I tell you about…' style questions, check the memory list "
    "in this prompt first; if not present, call recall_memory.\n"
    "8. For questions that sound like 'according to our docs', 'what does the X "
    "policy say', 'find me the contract for Y', or any time the answer likely "
    "lives in a stored document — ALWAYS call search_documents first and cite "
    "the source filename(s) in your reply.\n"
    "8a. INDEX-ON-DEMAND: If the user says things like 'index the Q3 report "
    "from my Drive', 'add this file to memory', 'index the Contracts folder "
    "on OneDrive', or asks a question about a SPECIFIC named file that "
    "search_documents returned 0 results for — find the file/folder with "
    "list_drive_files (or list_onedrive_files), get its id, then call "
    "index_drive_file / index_drive_folder / index_onedrive_file / "
    "index_onedrive_folder. After indexing returns, IMMEDIATELY call "
    "search_documents to answer the user's original question in the same "
    "turn. Tell the user the chunk_count so they know it worked.\n"
    "8b. PDF METADATA: If the user asks about page count, file size, or "
    "whether a PDF is scanned, call get_pdf_info (NOT search_documents). "
    "Report page_count, size, and let them know if has_extractable_text=false "
    "(scanned PDF — OCR will run automatically when they ask you to index "
    "it; takes ~30-60s for long scans).\n"
    "8b2. SPREADSHEET STRUCTURE: If the user asks how many sheets/tabs a "
    "file has, or wants sheet names, this is a STRUCTURAL question, not a "
    "content question — NEVER call search_documents for it, not even once, "
    "no matter how you phrase the query. For an uploaded .xlsx/.xls file, "
    "call get_spreadsheet_info(file_name=<the filename the user mentioned>) "
    "as your ONLY tool call — it resolves the file itself from what's "
    "already indexed, so skip list_drive_files/list_onedrive_files. For a "
    "native Google Sheet call list_sheet_tabs instead.\n"
    "8c. SEND FILE TO USER: When the user says 'send me the PDF', 'download "
    "X', 'give me the file', 'share with me' — they mean THEMSELVES, not "
    "another recipient. NEVER ask 'what email address?' — instead call "
    "send_file_to_user(file_id, source). On Telegram the file appears as a "
    "document attachment; on web a download link comes back. Find the file "
    "id with list_drive_files / list_onedrive_files FIRST. Only ask for a "
    "recipient email if the user explicitly says 'share with <someone>' or "
    "names another person.\n"
    "9. CALENDAR EVENT UPDATES: When you need to update or delete a calendar event, "
    "NEVER rely on an event ID from a previous turn or from memory — IDs can be "
    "stale or wrong. Instead, ALWAYS call read_calendar first to find the event "
    "by its title/summary, get the correct event ID from the result, THEN call "
    "update_calendar_event or delete_calendar_event with that ID.\n"
    "10. GMAIL REPLY CHECKING: When the user asks 'any reply to the email I "
    "just sent' or similar, call read_gmail with query 'newer_than:1h' and a "
    "high limit (25+) to catch the reply. Also try searching by the sender's "
    "email address. Do not just search by thread ID.\n"
    "11. DOCUMENTS: If the user asks about a specific file (PDF, DOCX, etc.) "
    "and search_documents returns no results, it likely means the file isn't "
    "indexed yet. Try list_drive_files to find it, then tell the user: "
    "'I found [filename] in your Drive but it hasn't been indexed yet. "
    "You can index it at /dashboard/documents so I can search its contents.' "
    "NEVER say you 'cannot access' or 'cannot read' a file type.\n"
    "12. You MUST always provide a text response. Never return an empty response. "
    "If a tool returns an error or no data, explain the situation to the user.\n"
    "13. WRITE OPS: NEVER hallucinate or guess email addresses, phone numbers, "
    "or other contact details. If the user doesn't provide them, use list_google_contacts "
    "to find them. If not found, ASK the user. NEVER send an invite to a "
    "placeholder like pole@example.com.\n"
    "14. GMAIL/OUTLOOK TIME QUERIES: You have ABSOLUTELY NO TIME LIMITS. "
    "NEVER claim you cannot search beyond a certain date. NEVER answer 'no "
    "emails' without first calling the tool with the correct arguments.\n"
    "    For Gmail 'yesterday' / 'last N days': use a query like "
    "'newer_than:2d' or 'after:YYYY/MM/DD' with limit 50.\n"
    "    For Outlook 'yesterday' / 'last N days' (e.g. 'mails in last 30 "
    "days', 'last 7 days', 'recent mail'): you MUST call read_outlook with "
    "query='' (EMPTY STRING), limit=50, and max_days_old=N (e.g. 30 for last "
    "30 days, 7 for last week, 1 for yesterday). DO NOT put the date in the "
    "query string — Outlook's $search does not support that. DO NOT filter "
    "dates yourself.\n"
    "    Be DETERMINISTIC: the same user question must produce the same tool "
    "call every time. If you got results last turn and the user asks the "
    "same thing this turn, call the tool with the same parameters — never "
    "say 'no emails' if you didn't actually search.\n"
    "15. AMBIGUOUS 'MAIL' REQUESTS: When the user says 'mails', 'emails', or "
    "'inbox' WITHOUT specifying Gmail or Outlook, check BOTH by calling "
    "read_gmail AND read_outlook in the same turn. Present results grouped by "
    "source: '📧 Gmail:' and '📬 Outlook:'. If one source has no results or "
    "is not connected, say so briefly and still show the other.\n"
    "16. EMAIL SUMMARY FORMAT: NEVER give lazy one-line summaries. For EVERY "
    "email, always include ALL of these details:\n"
    "   • Source (Gmail / Outlook)\n"
    "   • Full sender name and email address\n"
    "   • Subject line (complete, not truncated)\n"
    "   • Date and time received\n"
    "   • Short snippet/preview (1-2 lines)\n"
    "   Format each email as a numbered list with clear separation.\n"
    "17. CONSISTENCY ACROSS SURFACES: Your answer quality must be IDENTICAL on "
    "the web dashboard and on Telegram. Do NOT shorten, truncate, or simplify "
    "replies just because the channel is Telegram. Same depth, same detail, "
    "same number of items, same markdown formatting. The user is the same "
    "person on both surfaces — give them the same intelligent comprehensive "
    "assistant every time.\n"
    "18. NO LAZY ANSWERS: When the user asks an open question ('summarize my "
    "day', 'what should I focus on', 'brief me'), gather data from multiple "
    "tools in parallel (calendar + gmail + tasks at minimum), then synthesize "
    "a real briefing — not a one-line 'you have 3 events'. Always include "
    "what, when, who, and why-it-matters.\n"
    "19. NEVER INHERIT STALE ERRORS: If you see an error in conversation "
    "history (e.g. 'file is empty', 'cannot read', 'not connected'), DO NOT "
    "repeat it verbatim. Each turn is a fresh attempt — bugs may have been "
    "fixed since that earlier error. Always call the tool again. If it "
    "fails AGAIN this turn, only THEN explain the failure (and quote the "
    "current error, not the old one).\n"
    "20. SHARE + NOTIFY: When the user asks you to share a Drive/OneDrive "
    "file AND send a related email in the same request (e.g. 'share X with "
    "Y and email them asking to review it'), the share_drive_item / "
    "share_onedrive_item result includes 'file_name' and 'web_view_link' — "
    "you MUST include that link in the email body as a clickable reference "
    "(e.g. '[<file_name>](<web_view_link>)' or the raw URL), not just the "
    "message text the user dictated. A share notification without a link "
    "to the file is useless to the recipient.\n"
    "21. SCHEDULED TASK CONFIRMATION (applies to EVERY create_scheduled_task "
    "call, not just /schedule): once you have the topic, time, and channel, "
    "do NOT call create_scheduled_task yet. First reply with a plain-text "
    "recap of exactly what you're about to schedule — the prompt you'll "
    "run (quote it verbatim, don't paraphrase), the resolved cron time "
    "with AM/PM spelled out unambiguously (e.g. 'today at 8:15 PM, i.e. "
    "20:15'), and the delivery channel — then ask the user to confirm. "
    "Only call create_scheduled_task in the NEXT turn, after they say "
    "'yes'/'confirm'/equivalent. Never guess at an ambiguous time (e.g. "
    "'8.15 pm' typed without a clear AM/PM marker) and create the task "
    "anyway 'just in case' — resolve the ambiguity in the recap BEFORE "
    "creating anything. The 'prompt' argument must be built ONLY from "
    "what the user actually asked for in THIS request — never reuse or "
    "merge in the topic/prompt of a different existing scheduled task "
    "just because it's mentioned in memory or an earlier unrelated "
    "conversation.\n"
    "22. MEMORY CORRECTIONS: Memories shown to you in 'Things you remember' "
    "are dated and carry an id. If one is stale (its date is old and it's "
    "about something that can change — a connection status, an ongoing "
    "plan, a preference) and you're not sure it's still true, verify with "
    "a live tool call rather than asserting it as fact. If the user "
    "explicitly corrects a memory ('that's wrong', 'I moved', 'that's not "
    "true anymore', 'forget that'), call forget_memory with its id — don't "
    "just silently agree in text while leaving the wrong memory in place "
    "for next time. Only use an id you've actually seen in this "
    "conversation or in a recall_memory result; never guess one.\n"
    "23. SCHEDULED TASK vs EMAIL TRIGGER: these are different tools for "
    "different intents — do not conflate them. create_scheduled_task is "
    "TIME-based ('every morning at 8', 'every Friday'). create_email_trigger "
    "is CONDITION-based ('the moment I get an email from X', 'when an "
    "invoice arrives') — it has no time schedule, it fires when a matching "
    "email shows up, checked every minute. If the user's phrasing implies "
    "a recurring clock time, use create_scheduled_task; if it implies "
    "reacting to something happening, use create_email_trigger. The same "
    "confirm-and-recap rule (#21) applies to create_email_trigger too — "
    "recap the exact condition (sender/keyword), the prompt, and channel, "
    "and wait for confirmation before creating it.\n"
    "24. RECENTLY SHARED CONTENT: If the user just sent a photo, PDF, or "
    "other file earlier in THIS conversation and then refers to 'this', "
    "'that', or 'this job'/'this document' etc., assume they mean what "
    "they JUST shared — call read_full_document on it (matching by the "
    "filename Kin just confirmed indexing) BEFORE searching Gmail/Drive "
    "history for it. Don't burn tool-call rounds re-discovering something "
    "already in front of you. For a multi-step request like 'apply to "
    "this job' (read a job posting + the resume + compose + send), if "
    "you're missing something required (e.g. which email address to send "
    "to) ASK the user directly instead of guessing or searching endlessly.\n"
    "25. LANGUAGE: Always reply in the same language the user is writing "
    "in (Italian in, Italian out; English in, English out; etc.), "
    "regardless of the language of this system prompt or of tool output. "
    "If the user switches languages mid-conversation, switch with them on "
    "the very next reply. Tool call arguments (search queries, event "
    "titles, etc.) should still use whatever language makes sense for the "
    "underlying data — this rule is about your reply to the user, not "
    "tool inputs.\n"
)

app = create_app()


# ---------------------------------------------------------------------------
# Assistant runner — shared by Telegram + web
# ---------------------------------------------------------------------------


def _system_prompt_for(
    user: dict[str, Any], memory_snippet: str = "", history_summary: str = ""
) -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    # Custom system prompt is a Pro+ feature — a user who set one while paid
    # and then downgraded shouldn't keep it live; re-check plan on every use,
    # not just at write time.
    custom_prompt = user.get("system_prompt") if plan_for(user) in PRO_PLUS_PLANS else None
    base = (custom_prompt or DEFAULT_SYSTEM_PROMPT).format(today=today)

    # NOTE: every block below this point is per-user or per-query dynamic
    # content. Keep it all AFTER the fully-static instruction blocks (this
    # one + CRITICAL SCHEDULE + CALENDAR EVENT LINKS) rather than interleaved
    # — that keeps the static portion a byte-identical shared prefix across
    # every default-prompt user's request on a given day, which is what lets
    # Gemini's automatic prefix/context caching actually apply to it instead
    # of missing on the first dynamic character it hits. Pure reordering,
    # same final text — do not move tz_info/confirm_before_write back above
    # the static blocks.
    base += (
        "\n\nWEB SEARCH INSTRUCTION:\n"
        "You have real live internet access via the 'web_search' and 'read_webpage' tools — you are NOT limited "
        "to your training data and CAN fetch and read specific web pages. NEVER say you 'don't have access to "
        "the internet', can't browse, or can't access external websites/URLs — that is false, you have these "
        "tools right now.\n"
        "1. Whenever the user pastes/shares a URL and asks you to summarize, read, explain, or analyze it (or "
        "anything at that link), IMMEDIATELY call 'read_webpage' with that exact URL as the first thing you do — "
        "do not ask for permission, do not claim you can't, just call it.\n"
        "2. Call 'web_search' proactively (don't ask permission first) whenever a question involves current "
        "events, recent news, prices, scores, or any fact that could have changed or that you're not fully "
        "confident about — never answer from possibly-stale memory when a quick search would give a real answer.\n"
        "3. If a web_search result's snippet isn't enough, call 'read_webpage' on the most relevant URL for the "
        "full content. Cite sources by URL when you use them."
    )

    base += (
        "\n\nCRITICAL SCHEDULE INSTRUCTION:\n"
        "When the user wants to schedule a task (via /schedule command or natural language):\n"
        "1. If the request is vague or ambiguous, ASK CLARIFYING QUESTIONS first. Understand exactly what the user wants to schedule.\n"
        "2. REFINED PROMPT FOR REMINDERS: When calling 'create_scheduled_task', write a clean, direct task prompt (e.g. 'Deliver a clear, friendly reminder to call the insurance agent. Keep it concise, helpful, and direct.').\n"
        "3. ACCURACY & NO HALLUCINATION: When running tools to verify details, NEVER fabricate search results. If no results are found, state so briefly.\n"
        "4. RELEVANCY: Do NOT dump unrelated recent inbox messages or diagnostic search dumps into the chat transcript.\n"
        "5. CHANNEL SELECTION: Ask the user which delivery channel they prefer (Email or Web Chat) unless they explicitly specified one.\n"
        "6. CONFIRMATION & EXECUTION: ONLY after the user selects a channel and confirms, call 'create_scheduled_task' with the refined prompt and chosen channel.\n"
        "7. LINKS: After successfully calling 'create_scheduled_task' (a reminder/automation, NOT a social media "
        "post — see SOCIAL POST SCHEDULING INSTRUCTION for that), output clickable markdown links:\n"
        "   - To view reminder schedules: `[📅 View in Schedules](/dashboard/schedule)`\n"
        "   - To test the schedule right now: `[🧪 Test Now](test-schedule:<task_id>)`\n"
        "   Do NOT output this /dashboard/schedule link after 'create_social_post' — that's a different page and "
        "confuses the user; see the social instruction below for the right link there.\n"
    )

    base += (
        "\n\nCALENDAR EVENT LINKS:\n"
        "After 'create_calendar_event' (or 'create_outlook_event') succeeds, its result includes a real "
        "'html_link' field — the actual Google/Outlook calendar URL for that event. ALWAYS include this exact "
        "link in your confirmation message as a markdown link, e.g. `[View in Calendar](<html_link value>)`, "
        "so it's saved in the conversation and available if the user asks for it again later. "
        "NEVER fabricate, guess, or reconstruct a calendar link yourself (e.g. inventing an 'eid=' parameter) — "
        "only ever output the exact URL the tool returned. If a user asks for the link later and you don't see "
        "a real one anywhere earlier in this conversation, say you don't have it and offer to look up the event "
        "again (read_calendar / get_calendar_event) instead of making one up."
    )
    base += (
        "\n\nGOOGLE SHEETS INSTRUCTION:\n"
        "When the user shares a Google Sheets URL or asks for sheet content (e.g. 'content?', 'first 10 rows', 'what are the sheet names?'):\n"
        "1. DO NOT ask the user to type cell range syntax like 'Sheet1!A1:E10'.\n"
        "2. CALL TOOLS IMMEDIATELY: Call 'list_sheet_tabs' to get tab names, or 'read_google_sheet(spreadsheet_id=..., range_a1=\"A1:Z10\")' immediately.\n"
        "3. PRESENT RESULTS CLEANLY: Format the values in a clear markdown table or bulleted list.\n"
    )

    user_tz = user.get("timezone") or "UTC"
    try:
        import pytz
        current_local_time = datetime.now(pytz.timezone(user_tz)).strftime("%A, %B %d, %Y at %I:%M %p (%Z, UTC%z)")
    except Exception:
        current_local_time = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
    base += (
        f"\n\nUser Profile Information:\nTimezone: {user_tz}\n"
        f"Current date and time RIGHT NOW in the user's timezone: {current_local_time}\n"
        "Use this exact value as 'now' — never guess or estimate the current time. When a tool call needs an "
        "ISO 8601 datetime (e.g. publish_date), compute it relative to this, in the user's timezone. When "
        "reporting any datetime back to the user (e.g. a post's scheduled publish time), convert it to the "
        "user's timezone and say it in plain language — never show a raw UTC/+00:00 timestamp."
    )

    if user.get("confirm_before_write"):
        base += (
            "\n\nCONFIRM BEFORE ACTING (user has this ON in Settings):\n"
            "Before calling ANY tool with a lasting real-world side effect — "
            "sending or replying to an email, sharing a file, creating/deleting "
            "a calendar event, deleting a scheduled task or memory, or any "
            "other write/mutating action — first reply with a plain-text recap "
            "of exactly what you're about to do (recipient, content, what gets "
            "created/deleted) and ask the user to confirm. Only call the tool "
            "in the NEXT turn, after they say yes/confirm. This applies on top "
            "of the scheduled-task confirmation rule above, not instead of it. "
            "Read-only actions (searching, listing, summarizing) never need "
            "confirmation — only ones that change something."
        )

    if history_summary:
        base += (
            "\n\nEARLIER IN THIS CONVERSATION (summarized — the raw messages "
            "have scrolled out of context, but treat these as things the user "
            "already told you; don't ask again or act like you're hearing them "
            "for the first time):\n" + history_summary
        )

    if memory_snippet:
        return f"{base}\n\n{memory_snippet}"
    return base


def _load_history(user_id: str, source: str, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    q = (
        supabase.table("messages")
        .select("role, content, created_at")
        .eq("user_id", user_id)
        .eq("source", source)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if session_id:
        q = q.eq("session_id", session_id)
    res = q.execute()
    return list(reversed(res.data or []))


async def _get_rolling_summary(
    user_id: str, source: str, session_id: str, window: int = 20
) -> str:
    """Keeps a compact running summary of everything OLDER than _load_history's
    raw window, so long conversations degrade gracefully instead of earlier
    context just disappearing once a chat passes ~20 messages. Cheap on most
    turns — only makes an LLM call when there's new "old" content to fold in
    that hasn't been summarized yet; otherwise just returns the stored text."""
    sess_key = session_id or ""
    try:
        count_q = supabase.table("messages").select("id", count="exact", head=True).eq("user_id", user_id).eq("source", source)
        if session_id:
            count_q = count_q.eq("session_id", session_id)
        total = count_q.execute().count or 0
        if total <= window:
            return ""  # nothing has scrolled out of the raw window yet

        row_res = (
            supabase.table("chat_history_summaries")
            .select("summary, summarized_through")
            .eq("user_id", user_id).eq("source", source).eq("session_id", sess_key)
            .maybeSingle().execute()
        )
        existing = row_res.data or {}
        existing_summary = existing.get("summary") or ""
        summarized_through = existing.get("summarized_through")

        # Capped at 500 to bound cost on pathologically long histories — if a
        # conversation somehow has thousands of messages, this only looks at
        # the oldest 500 per pass rather than trying to summarize all of it
        # in one shot; it'll catch up over subsequent turns.
        msgs_q = supabase.table("messages").select("role, content, created_at").eq("user_id", user_id).eq("source", source)
        if session_id:
            msgs_q = msgs_q.eq("session_id", session_id)
        all_msgs = msgs_q.order("created_at", desc=False).limit(500).execute().data or []

        old_msgs = all_msgs[:-window] if len(all_msgs) > window else []
        new_old_msgs = [
            m for m in old_msgs if not summarized_through or m["created_at"] > summarized_through
        ]
        if not new_old_msgs:
            return existing_summary  # already caught up, no LLM call needed

        transcript = "\n".join(
            f"{m['role']}: {(m.get('content') or '')[:500]}" for m in new_old_msgs
        )
        prompt = (
            "You maintain a compact running summary of an ongoing assistant "
            "conversation, so older turns can be dropped from the raw context "
            "without losing continuity.\n\n"
            f"Existing summary (may be empty):\n{existing_summary or '(none yet)'}\n\n"
            f"New older messages to fold in:\n{transcript}\n\n"
            "Write an updated summary under 250 words. Preserve concrete facts, "
            "decisions, names, dates, and open tasks the assistant would need "
            "to recall later. Drop small talk and resolved back-and-forth. "
            "Return ONLY the summary text, no preamble."
        )
        resp = await llm_complete(
            model="gemini-2.5-flash-lite",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
            feature="rolling_summary",
            user_id=user_id,
        )
        new_summary = (resp.text or existing_summary or "").strip()
        supabase.table("chat_history_summaries").upsert(
            {
                "user_id": user_id,
                "source": source,
                "session_id": sess_key,
                "summary": new_summary,
                "summarized_through": new_old_msgs[-1]["created_at"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id,source,session_id",
        ).execute()
        return new_summary
    except Exception:
        logger.exception("Failed to update rolling history summary for user %s", user_id)
        return ""


def _persist(**fields) -> None:
    # Ensure source field is safe if invalid or custom channel value is passed
    valid_sources = {"web", "cron", "email", "api"}
    if "source" in fields and fields["source"]:
        raw_source = str(fields["source"]).lower()
        if raw_source not in valid_sources:
            if "email" in raw_source:
                fields["source"] = "email"
            elif "cron" in raw_source or "scheduled" in raw_source:
                fields["source"] = "cron"
            else:
                fields["source"] = "web"
    supabase.table("messages").insert(fields).execute()



_VOICE_BUCKET = "kin-voice-messages"
_VOICE_URL_TTL = 60 * 60 * 24 * 365  # 1 year — long enough that "reopen an old
# chat" effectively never hits an expired link, without going as far as a
# fully public bucket for what can be personal audio content.
_AUDIO_EXT_BY_MIME = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
}


def _store_voice_message(
    user_id: str, session_id: str, audio_bytes: bytes, audio_mime: Optional[str]
) -> Optional[str]:
    """Upload a recorded voice message so it survives page reloads / re-opening
    an old chat from history — previously the audio only ever lived in the
    browser's in-memory blob URL for that one page load, then was gone."""
    try:
        try:
            supabase.storage.create_bucket(_VOICE_BUCKET, options={"public": False})
        except Exception:  # noqa: BLE001
            pass  # already exists
        base_mime = (audio_mime or "audio/webm").split(";")[0].strip().lower()
        ext = _AUDIO_EXT_BY_MIME.get(base_mime, "webm")
        path = f"{user_id}/{session_id}/{uuid.uuid4().hex[:12]}.{ext}"
        supabase.storage.from_(_VOICE_BUCKET).upload(
            path, audio_bytes, {"content-type": audio_mime or "audio/webm"}
        )
        signed = supabase.storage.from_(_VOICE_BUCKET).create_signed_url(path, _VOICE_URL_TTL)
        return signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL")
    except Exception:  # noqa: BLE001
        logger.exception("failed to store voice message audio")
        return None


MAX_TOOL_ROUNDS = 6
# Ordered fallback chain tried in sequence whenever a model call fails
# (quota/429, transient 5xx, or any other error) — the free-tier AI Studio
# key's daily quota varies wildly per model (e.g. 20 RPD on gemini-2.5-flash
# vs 500 RPD on gemini-3.1-flash-lite), so a single fallback isn't enough to
# ride out a busy day. Gemini 3.x models require a thought_signature on
# every function-call part in a multi-turn conversation, which our manual
# tool-calling loop doesn't propagate — if a later round in an ongoing
# conversation breaks on one of those for that reason, it's just another
# failure this same chain retries past, landing back on a 2.5 model (no
# signature requirement) for that round instead of hard-failing.
GEMINI_FALLBACK_MODELS: list[str] = [
    m.strip() for m in os.environ.get(
        "KIN_FALLBACK_MODELS",
        "gemini-2.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3-flash",
    ).split(",") if m.strip()
]
# Back-compat: some call sites/log messages still refer to a single fallback name.
GEMINI_FALLBACK_MODEL = GEMINI_FALLBACK_MODELS[0] if GEMINI_FALLBACK_MODELS else "gemini-2.5-flash"

# Tool calls with a lasting real-world side effect (sends something, creates
# a recurring automation, deletes something) that we refuse to let the
# weaker fallback model execute unsupervised — see the fallback-model write
# guard in run_assistant. A bad read is annoying; a bad write persists.
SENSITIVE_WRITE_TOOLS = frozenset({
    "create_scheduled_task",
    "delete_scheduled_task",
    "send_email",
    "reply_email",
    "reply_to_thread",
    "send_followup_nudge",
    "draft_email",
    "trash_email",
    "delete_email_permanent",
    "send_outlook_email",
    "reply_outlook_email",
    "delete_outlook_message",
    "share_drive_item",
    "share_onedrive_item",
    "create_calendar_event",
    "delete_calendar_event",
    "create_outlook_event",
    "delete_outlook_event",
    "declutter_gmail_sender",
    "create_email_trigger",
    "delete_email_trigger",
})

# ---------------------------------------------------------------------------
# Plans / quotas — monthly message count enforced on /api/chat + telegram.
# Free covers evaluation; paid tiers cover real use.
# ---------------------------------------------------------------------------

PLAN_QUOTAS: dict[str, int] = {
    # Kept for plan_for()'s key-membership check (and because the
    # users_plan_check DB constraint — 20260719000000_chatty_billing_plans.sql
    # — still allows the chatty_* values below, so an existing row with one
    # of those must still validate here even though the message-count quota
    # itself is not enforced anywhere for Kin's own chat/API; Kin's own
    # quota gate uses KIN_TOKEN_QUOTAS below instead). The Chatty widget
    # product these chatty_* tiers were for was never actually built (no
    # /api/widget/* route exists anywhere in this codebase — see the
    # app_factory.py Widget-tag cleanup) — chatty_quota_exceeded() and
    # get_chatty_monthly_usage(), which used to reference this dict for
    # that product, were removed as dead code during security-audit
    # remediation. Left here rather than removed outright since the DB
    # constraint and plan_for()'s fallback logic still depend on these keys
    # existing for any account that already has one of these plan values.
    "free": 100,
    "basic": 500,
    "pro": 3000,
    "executive": 15000,
    # Chatty-specific tiers — quotas match what's advertised on chatty's own
    # pricing page (src/app/page.tsx): $19/$99/$399 for 1k/10k/40k msgs/mo.
    "chatty_hobby": 1000,
    "chatty_standard": 10000,
    "chatty_business": 40000,
}

# Real Kin quota gate, replacing the message-count model above (found
# 2026-07-20 to be structurally loss-making: a "message" can trigger 1-6
# internal Gemini calls depending on tool-calling complexity, so message
# count has near-zero correlation with actual LLM cost — a user asking
# simple questions and a user running multi-step agentic tasks paid the
# same price for wildly different cost). Token counts are billed at Gemini
# 3.5 Flash's real rates ($1.50/1M input, $9.00/1M output, ~$0.15/1M for
# cache-hit input — Gemini's automatic implicit caching already covers
# 65-96% of input tokens in production since the tool manifest + system
# prompt form a stable repeated prefix). These numbers target ~75% gross
# margin on LLM cost alone at FULL quota utilization, not just on average.
KIN_TOKEN_QUOTAS: dict[str, int] = {
    "free": 1_000_000,
    "basic": 3_000_000,
    "pro": 10_000_000,
    "executive": 30_000_000,
}

# Plans allowed to white-label (remove the "Powered by Chatty" mark).
WHITELABEL_PLANS = {"pro", "executive", "chatty_business"}

# Kin plan-gated features. These used to be advertised on pricing but only
# the message quota was actually enforced anywhere — audited and fixed.
PAID_PLANS = {"basic", "pro", "executive"}       # daily briefing, voice
PRO_PLUS_PLANS = {"pro", "executive"}             # custom system prompt
PRIORITY_PLANS = {"pro", "executive"}             # more retries before
# falling back to the weaker model under capacity contention

# Retry attempts on the primary model before falling back to the lite one
# (see _gemini_generate) — Executive gets a real edge over Pro here, not
# just a bigger quota number.
_PRIORITY_ATTEMPTS = {"executive": 8, "pro": 6}

# API keys and webhooks moved from Executive-only to free-for-everyone (with
# these count caps, since neither had one before — actual request volume was
# already bounded by the normal per-plan KIN_TOKEN_QUOTAS and chat.py's
# existing 60 req/min-per-key / 120 req/min-per-IP rate limits regardless of
# plan, so the only real new abuse surface opening this up creates is
# unbounded key/webhook *count*, not unbounded usage).
MAX_KIN_API_KEYS = 5
MAX_KIN_WEBHOOKS = 5


def priority_attempts(plan: str) -> int:
    return _PRIORITY_ATTEMPTS.get(plan, 4)


def _month_start_iso() -> str:
    now = datetime.now(tz=timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def plan_for(user: dict[str, Any]) -> str:
    plan = (user.get("plan") or "free").lower()
    return plan if plan in PLAN_QUOTAS else "free"


def _fmt_tokens(n: int) -> str:
    """1000000 -> '1M', 3500000 -> '3.5M' — for user-facing quota messages."""
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{v:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def quota_state(user: dict[str, Any], _usage: Optional[dict[str, int]] = None) -> tuple[int, int]:
    """Return (tokens_used_this_month, token_limit). Falls back to the Free
    token quota for a plan value KIN_TOKEN_QUOTAS doesn't recognize (e.g. a
    Chatty-only plan like chatty_hobby, if that account also messages Kin
    directly) rather than raising.

    Pass `_usage` (an already-fetched get_monthly_token_usage() result) when
    the caller needs that dict anyway — e.g. GET /api/usage, which used to
    call get_monthly_token_usage() a second time right after this, doubling
    the RPC round trip for no reason."""
    limit = KIN_TOKEN_QUOTAS.get(plan_for(user), KIN_TOKEN_QUOTAS["free"])
    usage = _usage if _usage is not None else get_monthly_token_usage(user["id"])
    return usage["total_tokens"], limit


def _sanitize_contents(raw_contents: list) -> list:
    cleaned = []
    for item in (raw_contents or []):
        if not item:
            continue
        parts = getattr(item, "parts", None)
        if parts is not None:
            valid_parts = []
            for p in parts:
                if not p:
                    continue
                has_content = (
                    bool(getattr(p, "text", None))
                    or bool(getattr(p, "function_call", None))
                    or bool(getattr(p, "function_response", None))
                    or bool(getattr(p, "inline_data", None))
                    or bool(getattr(p, "file_data", None))
                    or bool(getattr(p, "thought", None))
                )
                if has_content:
                    valid_parts.append(p)
            if valid_parts:
                item.parts = valid_parts
                cleaned.append(item)
        else:
            cleaned.append(item)
    return cleaned or raw_contents


async def _gemini_generate(
    *, model: str, contents: list, config: genai_types.GenerateContentConfig, max_attempts: int = 4
):
    contents = _sanitize_contents(contents)
    transient = (429, 502, 503, 504)
    last_err: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            resp = await genai_client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
            logger.info("Gemini raw response (%s): %s", model, resp)
            return resp
        except genai_errors.ServerError as exc:
            last_err = exc
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code not in transient or attempt == max_attempts - 1:
                break
            backoff = (2 ** attempt) * (1 + random.uniform(-0.2, 0.2))
            logger.warning(
                "gemini %s transient %s — retry %d/%d in %.1fs",
                model, code, attempt + 1, max_attempts, backoff,
            )
            await asyncio.sleep(backoff)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            break

    # Fallback chain — different models/shards, often available when the
    # primary is exhausted. Tried in order until one works.
    for fallback_model in GEMINI_FALLBACK_MODELS:
        if fallback_model == model:
            continue
        logger.warning("falling back from %s to %s", model, fallback_model)
        try:
            return await genai_client.aio.models.generate_content(
                model=fallback_model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    assert last_err is not None
    raise last_err


async def _gemini_stream(
    *,
    model: str,
    contents: list,
    config: genai_types.GenerateContentConfig,
    on_token=None,
):
    contents = _sanitize_contents(contents)
    """Streaming counterpart to _gemini_generate.

    Iterates streamed chunks, invoking ``await on_token(delta)`` for each visible
    text delta (skip when None to just aggregate). Returns a normalized dict:
    ``{text, function_calls, model_content, thinking}`` so the tool-calling loop
    can treat it exactly like a finished response. Falls back to the fallback
    model, then to the non-streaming path, on any streaming error — so streaming
    never makes a request fail that would otherwise have succeeded.
    """

    async def _run(m: str) -> dict:
        stream = await genai_client.aio.models.generate_content_stream(
            model=m, contents=contents, config=config
        )
        text_parts: list[str] = []
        fcs: list = []
        model_parts: list = []
        thinking: list[str] = []
        async for chunk in stream:
            for cand in (chunk.candidates or []):
                if not cand.content:
                    continue
                for part in (cand.content.parts or []):
                    fc = getattr(part, "function_call", None)
                    if fc:
                        fcs.append(fc)
                        model_parts.append(part)
                    elif getattr(part, "thought", False) and getattr(part, "text", None):
                        thinking.append(part.text)
                    elif getattr(part, "text", None):
                        text_parts.append(part.text)
                        model_parts.append(part)
                        if on_token:
                            await on_token(part.text)
        return {
            "text": "".join(text_parts).strip(),
            "function_calls": fcs,
            "model_content": genai_types.Content(role="model", parts=model_parts) if model_parts else None,
            "thinking": "\n\n".join(thinking),
        }

    try:
        return await _run(model)
    except Exception:  # noqa: BLE001
        logger.exception("gemini stream failed on %s", model)
        for fallback_model in GEMINI_FALLBACK_MODELS:
            if fallback_model == model:
                continue
            try:
                return await _run(fallback_model)
            except Exception:  # noqa: BLE001
                logger.exception("gemini stream fallback failed on %s", fallback_model)
        # Last resort: non-streaming call (has its own retry + full chain fallback).
        resp = await _gemini_generate(model=model, contents=contents, config=config)
        cand = (resp.candidates or [None])[0]
        parts = (cand.content.parts if cand and cand.content else []) or []
        fcs = [p.function_call for p in parts if getattr(p, "function_call", None)]
        text = (resp.text or "").strip()
        if on_token and text and not fcs:
            await on_token(text)
        return {
            "text": text,
            "function_calls": fcs,
            "model_content": (cand.content if cand and cand.content else None),
            "thinking": _extract_thinking(resp),
        }


def _extract_usage(response) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) from a Gemini response, or (0, 0) if
    the SDK didn't return usage_metadata (e.g. mid-stream chunks)."""
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return 0, 0
    return (
        getattr(meta, "prompt_token_count", None) or 0,
        getattr(meta, "candidates_token_count", None) or 0,
    )


def _extract_thinking(response) -> str:
    """Extract thinking/reasoning text from a Gemini response."""
    parts = []
    try:
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                if getattr(part, "thought", False) and part.text:
                    parts.append(part.text.strip())
    except Exception:  # noqa: BLE001
        pass
    return "\n\n".join(parts)


async def run_assistant(
    *,
    user: dict[str, Any],
    text: str,
    audio_bytes: Optional[bytes],
    audio_mime: Optional[str],
    source: str,
    session_id: str,
    tool_context: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    """Run a single assistant turn with multi-step tool-calling + RAG memory.

    Returns dict with 'reply' and 'thinking' keys.

    Persists the user's message immediately. Retrieves top-k similar memories
    via pgvector and injects them into the system prompt. Loops up to
    MAX_TOOL_ROUNDS times. Persists the final reply + a JSON trace of which
    tools were used.
    """
    user_id = user["id"]
    # Pro/Executive: more retry headroom on the smart model before ever
    # falling back to the weaker one under capacity contention (see
    # _gemini_generate) — a real "priority processing" benefit, not a
    # marketing claim with nothing behind it.
    retry_attempts = priority_attempts(plan_for(user))
    audio_url = _store_voice_message(user_id, session_id, audio_bytes, audio_mime) if audio_bytes else None
    _persist(
        user_id=user_id,
        role="user",
        content=text or ("[voice message]" if audio_bytes else ""),
        source=source,
        session_id=session_id,
        audio_url=audio_url,
    )

    # RAG: pull semantically similar memories from prior conversations and
    # inject them as system context. Skipped if memory is disabled or the
    # user message is too short to embed meaningfully (voice-only goes via tool).
    memory_snippet = ""
    if user.get("memory_enabled", True) and text and len(text.strip()) >= 8:
        try:
            mems = mem.retrieve(supabase, genai_client, user_id=user_id, query=text)
            memory_snippet = mem.format_for_prompt(mems)
        except Exception:  # noqa: BLE001 — never let memory retrieval break the turn
            logger.exception("memory retrieve failed")

    history = _load_history(user_id, source, session_id)
    try:
        history_summary = await _get_rolling_summary(user_id, source, session_id)
    except Exception:  # noqa: BLE001 — never let summarization break the turn
        logger.exception("rolling summary lookup failed")
        history_summary = ""
    contents: list[genai_types.Content] = []
    last_role: Optional[str] = None
    for row in history[:-1]:
        raw = (row.get("content") or "").strip()
        if not raw or raw == "[voice message]":
            continue
        role = "user" if row["role"] == "user" else "model"
        if role == last_role:
            contents[-1].parts.append(genai_types.Part.from_text(text=raw))
            continue
        contents.append(
            genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=raw)])
        )
        last_role = role
    while contents and contents[0].role != "user":
        contents.pop(0)

    prompt_text = text
    exclude_tools = []
    if text:
        stripped_text = text.strip()
        lower_text = stripped_text.lower()
        if lower_text.startswith("/schedule") or lower_text.startswith("/shedule") or lower_text.startswith("schedule"):
            exclude_tools.append("create_scheduled_task")
            space_idx = stripped_text.find(" ")
            cmd_content = stripped_text[space_idx:].strip() if space_idx != -1 else ""
            if not cmd_content:
                prompt_text = (
                    "INSTRUCTION: The user wants to schedule a task but did not specify any details. "
                    "Please reply asking them what task they want to schedule and at what time. "
                    "Provide a helpful example, such as: '/schedule Morning Briefing: Summarize my calendar and inbox at 7 AM'."
                )
            else:
                prompt_text = (
                    f"USER SCHEDULE REQUEST: {cmd_content}\n\n"
                    "INSTRUCTION: The user wants to schedule an automated task. "
                    "DO NOT immediately create it. First, analyze the request carefully:\n"
                    "1. Is the prompt clear and specific enough to produce useful output when run automatically? "
                    "If not, ask the user clarifying questions (e.g., 'what do you mean by analyze all send?').\n"
                    "2. Once the request is clear, first TEST the prompt by executing it yourself right now "
                    "(call the relevant tools like read_gmail, read_calendar, etc. as if you are running the prompt). "
                    "Show the user the test results so they can see what the scheduled task will produce.\n"
                    "3. Only AFTER showing the test results, you MUST explicitly ask the user which delivery channel they prefer. "
                    "Do NOT choose or assume a channel yourself. You MUST ask the user: "
                    "'These are the results. Should I schedule this to run automatically? And which channel would you like to receive it on: Email or Web Chat?'\n"
                    "4. ONLY after the user explicitly confirms and selects a channel (Email or Web Chat), THEN call 'create_scheduled_task' with the refined prompt and the selected channel (use 'email' for Email, 'web' for Web Chat, ). "
                    "You MUST NOT call 'create_scheduled_task' until the user has explicitly chosen the channel. "
                    "If they didn't specify a timezone, use the user's profile timezone.\n"
                    "5. After successfully calling 'create_scheduled_task', you MUST output the following two clickable markdown links in your final success message:\n"
                    "   - `[📅 View in Schedules](/dashboard/schedule)`\n"
                    "   - `[🧪 Test Now](test-schedule:<task_id>)` using the task's ID from the tool response.\n"
                    "DO NOT skip steps. DO NOT create the task without testing first and asking the user for their preferred channel."
                )
        elif stripped_text.startswith("/") and " " not in stripped_text.split(" ", 1)[0]:
            # Check saved custom commands (e.g. "/standup") before falling
            # through to the model's own slash-command autocomplete.
            cmd_name = stripped_text[1:].split(" ", 1)[0].strip().lower()
            space_idx = stripped_text.find(" ")
            extra_args = stripped_text[space_idx:].strip() if space_idx != -1 else ""
            if cmd_name:
                try:
                    cmd_res = (
                        supabase.table("custom_commands")
                        .select("prompt_template")
                        .eq("user_id", user_id)
                        .ilike("name", cmd_name)
                        .limit(1)
                        .execute()
                    )
                    if cmd_res.data:
                        template = cmd_res.data[0]["prompt_template"]
                        prompt_text = f"{template}\n\n{extra_args}" if extra_args else template
                except Exception:  # noqa: BLE001
                    logger.exception("custom command lookup failed for /%s", cmd_name)

    parts: list[genai_types.Part] = []
    if prompt_text:
        parts.append(genai_types.Part.from_text(text=prompt_text))
    if audio_bytes:
        parts.append(
            genai_types.Part.from_bytes(data=audio_bytes, mime_type=audio_mime or "audio/ogg")
        )
    if parts:
        contents.append(genai_types.Content(role="user", parts=parts))

    try:
        mcp_res = supabase.table("mcp_servers").select("*").eq("user_id", user_id).execute()
        mcp_servers = mcp_res.data or []
    except Exception:
        logger.exception("Failed to fetch user MCP servers")
        mcp_servers = []

    # KIN_USE_LITELLM=1 routes this turn's model calls through
    # app/core/llm.py (litellm) via the app/core/gemini_compat.py shim,
    # instead of genai_client directly. Off by default — see the
    # KIN_USE_LANGGRAPH branch and the manual-loop branch below for exactly
    # where this changes behavior. Stage 4 of the litellm migration; needs
    # live-credential verification before enabling in production (see
    # scripts/graph_parity_check.py).
    use_litellm = os.environ.get("KIN_USE_LITELLM", "").strip().lower() in ("1", "true", "yes")

    config = genai_types.GenerateContentConfig(
        system_instruction=_system_prompt_for(user, memory_snippet, history_summary),
        tools=[agent_tools.get_tool_config(mcp_servers, exclude_tools=exclude_tools, user_id=user_id, supabase=supabase, message_text=text or "")],
        # 4096 was too tight for multi-source replies: rule #16 mandates full
        # per-item detail (sender/subject/date/snippet) for every result, and
        # dual-source mail queries (Gmail + Outlook, up to 50 each = 100
        # items worst case) routinely exceeded it, truncating the reply
        # mid-sentence after the first source. 32768 comfortably covers even
        # the 100-item worst case (~190 tokens/verbose item observed).
        max_output_tokens=32768,
        temperature=0.2,
    )

    litellm_config: Optional[gemini_compat.types.GenerateContentConfig] = None
    if use_litellm:
        litellm_config = gemini_compat.types.GenerateContentConfig(
            system_instruction=_system_prompt_for(user, memory_snippet, history_summary),
            tools=agent_tools.get_openai_tool_config(
                mcp_servers, exclude_tools=exclude_tools, user_id=user_id,
                supabase=supabase, message_text=text or "",
            ),
            max_output_tokens=32768,
            temperature=0.2,
        )

    started = time.monotonic()
    tool_trace: list[dict[str, Any]] = []
    thinking_parts: list[str] = []
    usage_acc = {"prompt": 0, "completion": 0}

    def _track(resp) -> None:
        p, c = _extract_usage(resp)
        usage_acc["prompt"] += p
        usage_acc["completion"] += c

    # Ambiguous "mail/email/inbox" queries (no provider named) must check
    # BOTH Gmail and Outlook when both are connected — see system prompt
    # rule #15. The model doesn't reliably call both on its own, so detect
    # and force it deterministically rather than trusting instruction-
    # following alone.
    _user_lower = (text or "").lower().strip()
    _mentions_mail = any(k in _user_lower for k in ("mail", "email", "inbox"))
    _names_provider = any(
        k in _user_lower
        for k in ("gmail", "google mail", "outlook", "microsoft mail", "office 365", "hotmail")
    )
    _mail_read_verbs = ("read", "check", "search", "find", "show", "get", "list", "fetch", "unread", "recent", "any email", "my email", "my mail", "inbox")
    _is_search_intent = any(v in _user_lower for v in _mail_read_verbs)
    _is_channel_selection = _user_lower in ("email", "mail", "via email", "by email", "on email") or "schedule" in _user_lower or "reminder" in _user_lower
    is_ambiguous_mail_query = _mentions_mail and _is_search_intent and not _names_provider and not _is_channel_selection

    both_mail_connected = bool(user.get("google_access_token")) and bool(
        user.get("microsoft_access_token")
    )
    mail_retry_forced = False

    # --- LangGraph path (feature-flagged, not the default) -----------------
    # KIN_USE_LANGGRAPH=1 routes this turn through graph_agent.py's explicit
    # state machine instead of the manual for-loop below. Both call the same
    # _gemini_generate / agent_tools.execute primitives — this only swaps
    # the control flow, not the model or tool behavior. Off by default:
    # verify tool_trace parity against real traffic before enabling broadly.
    if os.environ.get("KIN_USE_LANGGRAPH", "").strip().lower() in ("1", "true", "yes"):
        try:
            if use_litellm:
                # KIN_USE_LITELLM + KIN_USE_LANGGRAPH both set: graph_agent.py
                # runs completely unmodified — only the identity of the
                # injected callables/types changes, from the real
                # google-genai primitives to the litellm-backed
                # app/core/gemini_compat.py shim. See that module's
                # docstring for exactly which google-genai surface it
                # mimics and its known gaps (no "thinking" parts, no inline
                # audio parts, retry/fallback delegated to litellm).
                graph_deps = {
                    "gemini_generate": gemini_compat.generate,
                    "extract_usage": _extract_usage,
                    "extract_thinking": _extract_thinking,
                    "execute_tool": agent_tools.execute,
                    "genai_types": gemini_compat.types,
                    "model_name": MODEL_NAME,
                    "fallback_models": GEMINI_FALLBACK_MODELS,
                    "sensitive_write_tools": SENSITIVE_WRITE_TOOLS,
                    "max_tool_rounds": MAX_TOOL_ROUNDS,
                    "retry_attempts": retry_attempts,
                    "config": litellm_config,
                    "config_final": gemini_compat.types.GenerateContentConfig(
                        system_instruction=_system_prompt_for(user, memory_snippet, history_summary)
                        + graph_agent._FINAL_NUDGE,
                        tools=litellm_config.tools,
                    ),
                    "user": user,
                    "supabase": supabase,
                    "genai_client": genai_client,
                    "source": source,
                    "session_id": session_id,
                    "tool_context": tool_context,
                    "is_ambiguous_mail_query": is_ambiguous_mail_query,
                    "both_mail_connected": both_mail_connected,
                }
            else:
                graph_deps = {
                    "gemini_generate": _gemini_generate,
                    "extract_usage": _extract_usage,
                    "extract_thinking": _extract_thinking,
                    "execute_tool": agent_tools.execute,
                    "genai_types": genai_types,
                    "model_name": MODEL_NAME,
                    "fallback_models": GEMINI_FALLBACK_MODELS,
                    "sensitive_write_tools": SENSITIVE_WRITE_TOOLS,
                    "max_tool_rounds": MAX_TOOL_ROUNDS,
                    "retry_attempts": retry_attempts,
                    "config": config,
                    "config_final": genai_types.GenerateContentConfig(
                        system_instruction=_system_prompt_for(user, memory_snippet, history_summary)
                        + graph_agent._FINAL_NUDGE,
                    ),
                    "user": user,
                    "supabase": supabase,
                    "genai_client": genai_client,
                    "source": source,
                    "session_id": session_id,
                    "tool_context": tool_context,
                    "is_ambiguous_mail_query": is_ambiguous_mail_query,
                    "both_mail_connected": both_mail_connected,
                }
            graph_result = await graph_agent.run(
                graph_deps,
                contents=contents,
                user_text=text or "",
            )
            _finalize(
                user, source, session_id, graph_result["reply"], started,
                graph_result["tool_trace"], graph_result["usage"],
            )
            return {"reply": graph_result["reply"], "thinking": graph_result["thinking"]}
        except Exception:
            logger.exception("graph_agent run failed")
            raise

    # --- litellm manual-loop path (feature-flagged, not the default) -------
    # KIN_USE_LITELLM=1 (without KIN_USE_LANGGRAPH) routes this turn through
    # a parallel copy of the manual for-loop below, calling
    # app/core/gemini_compat.py's litellm-backed generate()/types instead of
    # _gemini_generate()/genai_types directly. This is a deliberate,
    # near-line-for-line duplicate of the loop that follows — Stage 4 is
    # scoped to prove the litellm path out behind an instant-revert flag,
    # not to de-duplicate main.py's control flow (that's Stage 6, once this
    # path is proven against real traffic). Off by default.
    if use_litellm:
        try:
            for round_idx in range(MAX_TOOL_ROUNDS):
                response = await gemini_compat.generate(
                    model=MODEL_NAME, contents=contents, config=litellm_config,
                    max_attempts=retry_attempts,
                )
                _track(response)
                candidate = response.candidates[0] if response.candidates else None
                if not candidate or not candidate.content:
                    logger.warning(
                        "Empty litellm response (attempt 1). Retrying with nudge. "
                        "Text: %s, Candidates: %s",
                        response.text, response.candidates,
                    )
                    contents.append(
                        gemini_compat.types.Content(
                            role="user",
                            parts=[gemini_compat.types.Part.from_text(
                                text="Please respond to the user's last message. "
                                "If you encountered an error or have no data, explain "
                                "that to the user. Never leave the user without a reply."
                            )],
                        )
                    )
                    response = await gemini_compat.generate(
                        model=MODEL_NAME, contents=contents, config=litellm_config,
                        max_attempts=retry_attempts,
                    )
                    _track(response)
                    candidate = response.candidates[0] if response.candidates else None
                    if not candidate or not candidate.content:
                        reply = (
                            (response.text or "").strip()
                            or "I'm sorry, I wasn't able to process that. Could you try rephrasing your request?"
                        )
                        _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                        return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

                _thinking = _extract_thinking(response)
                if _thinking:
                    thinking_parts.append(_thinking)

                fcs = [p.function_call for p in (candidate.content.parts or []) if p.function_call]

                actual_model = getattr(response, "model_version", None) or MODEL_NAME
                is_fallback_model = (actual_model != MODEL_NAME) and (str(actual_model) in GEMINI_FALLBACK_MODELS)
                if fcs and is_fallback_model:
                    risky = [fc for fc in fcs if fc.name in SENSITIVE_WRITE_TOOLS]
                    if risky:
                        logger.warning(
                            "Blocked fallback-model (%s) write call(s): %s",
                            actual_model, [fc.name for fc in risky],
                        )
                        reply = (
                            "I'm at reduced capacity for a moment and don't want to risk "
                            "getting this wrong — could you send that request again? It'll "
                            "go through properly this time."
                        )
                        _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                        return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

                if not fcs:
                    reply = (response.text or "").strip()

                    if round_idx == 0 and reply:
                        reply_lower = reply.lower()
                        # Same detector phrase lists as the legacy loop below
                        # (kept inline here rather than hoisted to module
                        # scope, to avoid touching the legacy loop's code).
                        _refusal_phrases = (
                            "cannot fulfill", "i can only", "i'm sorry",
                            "i cannot", "i'm unable", "limited to",
                            "don't have the ability", "not supported",
                            "cannot access",
                        )
                        _empty_data_phrases = (
                            "no emails", "no email", "no messages", "no mail",
                            "no events", "no calendar", "no tasks", "no contacts",
                            "no files", "no documents",
                            "looks like there were no", "looks like there are no",
                            "you don't have any", "you do not have any",
                            "there are no", "there were no",
                            "your inbox is empty", "nothing in your",
                            "file might be empty", "file may be empty",
                            "file is empty", "appears to be empty",
                            "empty or corrupted", "appears to be corrupted",
                            "unable to determine", "unable to access",
                            "unable to read", "unable to get",
                            "cannot read", "cannot access", "cannot determine",
                            "still unable", "i apologize",
                        )
                        _tool_keywords = (
                            "mail", "email", "inbox", "gmail", "outlook",
                            "calendar", "event", "task", "contact",
                            "document", "drive", "file", "onedrive", "todo",
                            "pdf", "docx", "page", "pages", "indexed",
                            "send", "download",
                        )
                        user_lower = (text or "").lower()
                        is_refusal = any(p in reply_lower for p in _refusal_phrases)
                        claims_empty = any(p in reply_lower for p in _empty_data_phrases)
                        mentions_tool = any(k in user_lower for k in _tool_keywords)
                        needs_retry = mentions_tool and (is_refusal or claims_empty)
                        if needs_retry:
                            logger.warning(
                                "No-tool-call answer detected on round 0 (litellm path) "
                                "(refusal=%s, empty=%s). Reply: %s — Forcing retry.",
                                is_refusal, claims_empty, reply[:160],
                            )
                            contents.append(
                                gemini_compat.types.Content(
                                    role="user",
                                    parts=[gemini_compat.types.Part.from_text(
                                        text="STOP. You answered without calling a tool. "
                                        "IGNORE any prior errors in this conversation — bugs "
                                        "have been fixed since then. Retry the user's request "
                                        "by calling the right tool NOW with the correct "
                                        "arguments."
                                    )],
                                )
                            )
                            continue

                    if is_ambiguous_mail_query and both_mail_connected and not mail_retry_forced and reply:
                        called_tools = {t["tool"] for t in tool_trace}
                        missing_calls = []
                        if "read_gmail" not in called_tools:
                            missing_calls.append("read_gmail(query='', limit=50) for Gmail")
                        if "read_outlook" not in called_tools:
                            missing_calls.append(
                                "read_outlook(query='', limit=50, max_days_old=<N if time-based>) for Outlook"
                            )
                        if missing_calls:
                            mail_retry_forced = True
                            logger.warning(
                                "Ambiguous mail query only checked %d/2 sources (litellm path) — "
                                "forcing retry for: %s",
                                2 - len(missing_calls), missing_calls,
                            )
                            contents.append(
                                gemini_compat.types.Content(
                                    role="user",
                                    parts=[gemini_compat.types.Part.from_text(
                                        text=(
                                            "STOP. The user asked about mail/inbox without "
                                            "naming a provider, and both Gmail and Outlook are "
                                            "connected, but you only checked one source. Now "
                                            "call " + " and ".join(missing_calls)
                                            + ". Then present BOTH sources in your reply, "
                                            "grouped as '📧 Gmail:' and '📬 Outlook:' — if one "
                                            "has no results, say so briefly and still show the "
                                            "other."
                                        )
                                    )],
                                )
                            )
                            continue

                    if not reply:
                        logger.warning("No text parts in candidate (litellm path). Parts: %s", candidate.content.parts)
                        content_to_append = candidate.content
                        if not getattr(content_to_append, "role", None):
                            content_to_append.role = "model"
                        contents.append(content_to_append)
                        contents.append(
                            gemini_compat.types.Content(
                                role="user",
                                parts=[gemini_compat.types.Part.from_text(
                                    text="Your previous response was empty. Please provide "
                                    "a helpful text reply to the user. Summarize any tool "
                                    "results you received, or explain what happened."
                                )],
                            )
                        )
                        retry_resp = await gemini_compat.generate(
                            model=MODEL_NAME, contents=contents, config=litellm_config,
                            max_attempts=retry_attempts,
                        )
                        _track(retry_resp)
                        reply = (retry_resp.text or "").strip() or (
                            "I'm sorry, I wasn't able to process that. Could you try again?"
                        )
                    _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                    return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

                content_to_append = candidate.content
                if not getattr(content_to_append, "role", None):
                    content_to_append.role = "model"
                contents.append(content_to_append)

                tool_response_parts = []
                tool_results: list[dict] = []
                for fc in fcs:
                    args = dict(fc.args) if fc.args else {}
                    logger.info("tool call (litellm path): %s(%s)", fc.name, args)
                    result = await agent_tools.execute(
                        fc.name,
                        args,
                        user=user,
                        supabase=supabase,
                        genai_client=genai_client,
                        context={"source": source, "session_id": session_id, **(tool_context or {})},
                    )
                    tool_results.append(result)
                    tool_trace.append({"tool": fc.name, "args": args, "round": round_idx})
                    tool_response_parts.append(
                        gemini_compat.types.Part.from_function_response(
                            name=fc.name, response={"result": result}
                        )
                    )

                not_connected_errors = [
                    r for r in tool_results
                    if isinstance(r, dict) and "not connected" in str(r.get("error", "")).lower()
                ]
                if not_connected_errors and len(not_connected_errors) == len(tool_results):
                    err_msg = not_connected_errors[0].get("error", "")
                    if "microsoft" in err_msg.lower():
                        reply = (
                            "Your Microsoft account isn't connected yet. "
                            "Please visit /dashboard/integrations to connect your "
                            "Microsoft 365 account, then try again."
                        )
                    elif "google" in err_msg.lower():
                        reply = (
                            "Your Google account isn't connected yet. "
                            "Please visit /dashboard/integrations to connect your "
                            "Google account, then try again."
                        )
                    else:
                        reply = (
                            "The required service isn't connected yet. "
                            "Please visit /dashboard/integrations to connect it."
                        )
                    _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                    return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

                if tool_response_parts:
                    contents.append(gemini_compat.types.Content(role="user", parts=tool_response_parts))

            config_final_litellm = gemini_compat.types.GenerateContentConfig(
                system_instruction=_system_prompt_for(user, memory_snippet, history_summary)
                + graph_agent._FINAL_NUDGE,
                tools=litellm_config.tools,
            )
            final = await gemini_compat.generate(
                model=MODEL_NAME, contents=contents, config=config_final_litellm, max_attempts=retry_attempts
            )
            _track(final)
            if not (final.text or "").strip():
                contents.append(
                    gemini_compat.types.Content(
                        role="user",
                        parts=[gemini_compat.types.Part.from_text(
                            text="Your previous response was empty. You MUST reply with "
                            "plain text now — summarize what you found and ask the user "
                            "for whatever's missing to finish the request."
                        )],
                    )
                )
                final = await gemini_compat.generate(
                    model=MODEL_NAME, contents=contents, config=config_final_litellm, max_attempts=retry_attempts
                )
                _track(final)
            _thinking_final = _extract_thinking(final)
            if _thinking_final:
                thinking_parts.append(_thinking_final)
            reply = (final.text or "").strip() or (
                "I'm sorry, I wasn't able to complete that request. Could you try again?"
            )
            _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
            return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.exception("assistant error (litellm path)")
            _persist(
                user_id=user_id,
                role="assistant",
                content="(assistant error)",
                source=source,
                session_id=session_id,
                latency_ms=latency_ms,
                model=MODEL_NAME,
                error=str(exc),
                tool_calls=tool_trace or None,
                prompt_tokens=usage_acc["prompt"],
                completion_tokens=usage_acc["completion"],
                total_tokens=usage_acc["prompt"] + usage_acc["completion"],
            )
            raise

    try:
        for round_idx in range(MAX_TOOL_ROUNDS):
            response = await _gemini_generate(
                model=MODEL_NAME, contents=contents, config=config, max_attempts=retry_attempts
            )
            _track(response)
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                # Retry once with a nudge — the model sometimes returns empty
                # candidates on the first try, especially after tool results.
                logger.warning(
                    "Empty Gemini response (attempt 1). Retrying with nudge. "
                    "Text: %s, Candidates: %s",
                    response.text, response.candidates,
                )
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(
                            text="Please respond to the user's last message. "
                            "If you encountered an error or have no data, explain "
                            "that to the user. Never leave the user without a reply."
                        )],
                    )
                )
                response = await _gemini_generate(
                    model=MODEL_NAME, contents=contents, config=config, max_attempts=retry_attempts
                )
                _track(response)
                candidate = response.candidates[0] if response.candidates else None
                if not candidate or not candidate.content:
                    reply = (
                        (response.text or "").strip()
                        or "I'm sorry, I wasn't able to process that. Could you try rephrasing your request?"
                    )
                    _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                    return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

            # Collect thinking from this round
            _thinking = _extract_thinking(response)
            if _thinking:
                thinking_parts.append(_thinking)

            # Collect function calls (could be multiple in one response)
            fcs = [p.function_call for p in (candidate.content.parts or []) if p.function_call]

            # --- Fallback-model write guard ------------------------------------
            # The lite fallback model (used when the primary is rate-limited)
            # has proven capable of confidently hallucinating a WRONG argument
            # for a consequential write tool — e.g. creating a real recurring
            # scheduled task with content copied from an unrelated earlier
            # conversation instead of what the user actually just asked for.
            # A bad read is annoying; a bad write (an email sent, a task
            # scheduled) has a lasting side effect the user didn't approve.
            # Refuse to execute those specific calls when they came from the
            # fallback model — ask the user to retry instead of guessing.
            actual_model = getattr(response, "model_version", None) or MODEL_NAME
            is_fallback_model = (actual_model != MODEL_NAME) and (str(actual_model) in GEMINI_FALLBACK_MODELS)
            if fcs and is_fallback_model:
                risky = [fc for fc in fcs if fc.name in SENSITIVE_WRITE_TOOLS]
                if risky:
                    logger.warning(
                        "Blocked fallback-model (%s) write call(s): %s",
                        actual_model, [fc.name for fc in risky],
                    )
                    reply = (
                        "I'm at reduced capacity for a moment and don't want to risk "
                        "getting this wrong — could you send that request again? It'll "
                        "go through properly this time."
                    )
                    _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                    return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}


            if not fcs:
                reply = (response.text or "").strip()

                # --- Refusal / hallucinated-no-data detector ------------------
                # If round 0 mentions a tool-keyword in the user message but
                # the model answered without calling any tool, force a retry.
                # Two failure modes this catches:
                #   1. Explicit refusal ("I cannot access your data").
                #   2. Hallucinated empty answer ("no emails in the last 30
                #      days") when the model never actually called the tool.
                # The lite fallback model is especially prone to (2).
                if round_idx == 0 and reply:
                    reply_lower = reply.lower()
                    _REFUSAL_PHRASES = (
                        "cannot fulfill", "i can only", "i'm sorry",
                        "i cannot", "i'm unable", "limited to",
                        "don't have the ability", "not supported",
                        "cannot access",
                    )
                    _EMPTY_DATA_PHRASES = (
                        "no emails", "no email", "no messages", "no mail",
                        "no events", "no calendar", "no tasks", "no contacts",
                        "no files", "no documents",
                        "looks like there were no", "looks like there are no",
                        "you don't have any", "you do not have any",
                        "there are no", "there were no",
                        "your inbox is empty", "nothing in your",
                        # File/PDF stale-error patterns — model often
                        # hallucinates these from poisoned history.
                        "file might be empty", "file may be empty",
                        "file is empty", "appears to be empty",
                        "empty or corrupted", "appears to be corrupted",
                        "unable to determine", "unable to access",
                        "unable to read", "unable to get",
                        "cannot read", "cannot access", "cannot determine",
                        "still unable", "i apologize",
                    )
                    _TOOL_KEYWORDS = (
                        "mail", "email", "inbox", "gmail", "outlook",
                        "calendar", "event", "task", "contact",
                        "document", "drive", "file", "onedrive", "todo",
                        "pdf", "docx", "page", "pages", "indexed",
                        "send", "download",
                    )
                    user_lower = (text or "").lower()
                    is_refusal = any(p in reply_lower for p in _REFUSAL_PHRASES)
                    claims_empty = any(p in reply_lower for p in _EMPTY_DATA_PHRASES)
                    mentions_tool = any(k in user_lower for k in _TOOL_KEYWORDS)
                    needs_retry = mentions_tool and (is_refusal or claims_empty)
                    if needs_retry:
                        logger.warning(
                            "No-tool-call answer detected on round 0 "
                            "(refusal=%s, empty=%s). Reply: %s — Forcing retry.",
                            is_refusal, claims_empty, reply[:160],
                        )
                        contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[genai_types.Part.from_text(
                                    text=(
                                        "STOP. You answered without calling "
                                        "a tool. IGNORE any prior errors in "
                                        "this conversation — bugs have been "
                                        "fixed since then. Retry the user's "
                                        "request by calling the right tool "
                                        "NOW with the correct arguments:\n"
                                        "  • PDF page count / size / scan "
                                        "check: list_drive_files or "
                                        "list_onedrive_files to get file_id, "
                                        "then get_pdf_info(file_id, source).\n"
                                        "  • Send/download a file to user: "
                                        "send_file_to_user(file_id, source).\n"
                                        "  • Outlook 'last N days': "
                                        "read_outlook(query='', limit=50, "
                                        "max_days_old=N).\n"
                                        "  • Gmail 'last N days': "
                                        "read_gmail(query='newer_than:Nd', "
                                        "limit=50).\n"
                                        "  • Calendar: read_calendar (Google) "
                                        "or list_outlook_events (Microsoft).\n"
                                        "Do NOT apologize. Do NOT say 'no "
                                        "results' or 'unable'. Just call the "
                                        "tool."
                                    )
                                )],
                            )
                        )
                        continue
                # --- End detector --------------------------------------------

                # --- Dual-mail-source detector --------------------------------
                # Ambiguous "mail/email/inbox" query with both providers
                # connected: the model must call both read_gmail and
                # read_outlook (system prompt rule #15), but doesn't always.
                # Force it once if it only checked one source.
                if is_ambiguous_mail_query and both_mail_connected and not mail_retry_forced and reply:
                    called_tools = {t["tool"] for t in tool_trace}
                    missing_calls = []
                    if "read_gmail" not in called_tools:
                        missing_calls.append("read_gmail(query='', limit=50) for Gmail")
                    if "read_outlook" not in called_tools:
                        missing_calls.append(
                            "read_outlook(query='', limit=50, max_days_old=<N if time-based>) for Outlook"
                        )
                    if missing_calls:
                        mail_retry_forced = True
                        logger.warning(
                            "Ambiguous mail query only checked %d/2 sources — "
                            "forcing retry for: %s",
                            2 - len(missing_calls), missing_calls,
                        )
                        contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[genai_types.Part.from_text(
                                    text=(
                                        "STOP. The user asked about mail/inbox "
                                        "without naming a provider, and both "
                                        "Gmail and Outlook are connected, but "
                                        "you only checked one source. Now call "
                                        + " and ".join(missing_calls)
                                        + ". Then present BOTH sources in your "
                                        "reply, grouped as '📧 Gmail:' and "
                                        "'📬 Outlook:' — if one has no results, "
                                        "say so briefly and still show the other."
                                    )
                                )],
                            )
                        )
                        continue
                # --- End dual-mail-source detector ----------------------------

                if not reply:
                    # Same retry-with-nudge pattern for empty text responses
                    logger.warning("No text parts in candidate. Parts: %s", candidate.content.parts)
                    content_to_append = candidate.content
                    if not getattr(content_to_append, "role", None):
                        content_to_append.role = "model"
                    contents.append(content_to_append)
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(
                                text="Your previous response was empty. Please provide "
                                "a helpful text reply to the user. Summarize any tool "
                                "results you received, or explain what happened."
                            )],
                        )
                    )
                    retry_resp = await _gemini_generate(
                        model=MODEL_NAME, contents=contents, config=config, max_attempts=retry_attempts
                    )
                    _track(retry_resp)
                    reply = (retry_resp.text or "").strip() or (
                        "I'm sorry, I wasn't able to process that. Could you try again?"
                    )
                _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

            # Append the model's tool-call turn to the conversation
            content_to_append = candidate.content
            if not getattr(content_to_append, "role", None):
                content_to_append.role = "model"
            contents.append(content_to_append)

            # Execute each call and gather function_response parts
            tool_response_parts: list[genai_types.Part] = []
            tool_results: list[dict] = []
            for fc in fcs:
                args = dict(fc.args) if fc.args else {}
                logger.info("tool call: %s(%s)", fc.name, args)
                result = await agent_tools.execute(
                    fc.name,
                    args,
                    user=user,
                    supabase=supabase,
                    genai_client=genai_client,
                    context={"source": source, "session_id": session_id, **(tool_context or {})},
                )
                tool_results.append(result)
                tool_trace.append({"tool": fc.name, "args": args, "round": round_idx})
                tool_response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )

            # Short-circuit: if ALL tool results are "not connected" errors,
            # respond directly instead of sending back to Gemini (which tends
            # to return empty candidates for these error-only function_responses).
            not_connected_errors = [
                r for r in tool_results
                if isinstance(r, dict) and "not connected" in str(r.get("error", "")).lower()
            ]
            if not_connected_errors and len(not_connected_errors) == len(tool_results):
                err_msg = not_connected_errors[0].get("error", "")
                if "microsoft" in err_msg.lower():
                    reply = (
                        "Your Microsoft account isn't connected yet. "
                        "Please visit /dashboard/integrations to connect your "
                        "Microsoft 365 account, then try again."
                    )
                elif "google" in err_msg.lower():
                    reply = (
                        "Your Google account isn't connected yet. "
                        "Please visit /dashboard/integrations to connect your "
                        "Google account, then try again."
                    )
                else:
                    reply = (
                        "The required service isn't connected yet. "
                        "Please visit /dashboard/integrations to connect it."
                    )
                _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
                return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

            if tool_response_parts:
                contents.append(genai_types.Content(role="user", parts=tool_response_parts))

        # Exceeded MAX_TOOL_ROUNDS — force a final non-tool response. Multi-
        # step requests (e.g. "apply to this job" — needs the job details,
        # the resume, and a compose+send) can run out of rounds without
        # ever producing text; a second, more forceful nudge recovers most
        # of those instead of falling straight to the generic apology.
        FINAL_NUDGE = (
            "\n\nYou've already gathered enough data. Reply to the user now "
            "with a final answer; do not call any more tools. If you don't "
            "have everything needed to complete the request (e.g. a "
            "recipient email address), say what you found so far and ask "
            "the user for exactly what's missing — do NOT return nothing."
        )
        config_final = genai_types.GenerateContentConfig(
            system_instruction=_system_prompt_for(user, memory_snippet, history_summary) + FINAL_NUDGE,
        )
        final = await _gemini_generate(
            model=MODEL_NAME, contents=contents, config=config_final, max_attempts=retry_attempts
        )
        _track(final)
        if not (final.text or "").strip():
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(
                        text="Your previous response was empty. You MUST reply with "
                        "plain text now — summarize what you found and ask the user "
                        "for whatever's missing to finish the request."
                    )],
                )
            )
            final = await _gemini_generate(
                model=MODEL_NAME, contents=contents, config=config_final, max_attempts=retry_attempts
            )
            _track(final)
        _thinking_final = _extract_thinking(final)
        if _thinking_final:
            thinking_parts.append(_thinking_final)
        reply = (final.text or "").strip() or (
            "I'm sorry, I wasn't able to complete that request. Could you try again?"
        )
        _finalize(user, source, session_id, reply, started, tool_trace, usage_acc)
        return {"reply": reply, "thinking": "\n\n".join(thinking_parts)}

    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.exception("assistant error")
        _persist(
            user_id=user_id,
            role="assistant",
            content="(assistant error)",
            source=source,
            session_id=session_id,
            latency_ms=latency_ms,
            model=MODEL_NAME,
            error=str(exc),
            tool_calls=tool_trace or None,
            prompt_tokens=usage_acc["prompt"],
            completion_tokens=usage_acc["completion"],
            total_tokens=usage_acc["prompt"] + usage_acc["completion"],
        )
        raise


def _finalize(
    user: dict[str, Any],
    source: str,
    session_id: str,
    reply: str,
    started: float,
    tool_trace: list[dict[str, Any]],
    usage_acc: dict[str, int],
) -> None:
    latency_ms = int((time.monotonic() - started) * 1000)
    _persist(
        user_id=user["id"],
        role="assistant",
        content=reply,
        source=source,
        session_id=session_id,
        latency_ms=latency_ms,
        model=MODEL_NAME,
        tool_calls=tool_trace or None,
        prompt_tokens=usage_acc["prompt"],
        completion_tokens=usage_acc["completion"],
        total_tokens=usage_acc["prompt"] + usage_acc["completion"],
    )
    if plan_for(user) == "executive":
        asyncio.create_task(
            _dispatch_kin_webhooks(
                user["id"],
                "message.created",
                {"source": source, "session_id": session_id, "reply": reply},
            )
        )


# ---------------------------------------------------------------------------
# Google OAuth — Calendar + Gmail read-only
# ---------------------------------------------------------------------------


_oauth_state_secret_warned = False


def _oauth_state_secret() -> str:
    """OAUTH_STATE_SECRET if set; otherwise FUNCTION_SECRET, logged once.

    Decouples OAuth-state JWT signing from FUNCTION_SECRET (which also
    gates /cron/*, /admin/*, /internal/*, and doubles as the Telegram
    webhook query secret) — added during security-audit remediation so a
    leak of one doesn't compromise the other. Falls back so nothing breaks
    before OAUTH_STATE_SECRET is actually set in the deploy config.
    """
    global _oauth_state_secret_warned
    if OAUTH_STATE_SECRET:
        return OAUTH_STATE_SECRET
    if not _oauth_state_secret_warned:
        logger.warning(
            "OAUTH_STATE_SECRET is not set — falling back to FUNCTION_SECRET "
            "for OAuth-state JWT signing. Set OAUTH_STATE_SECRET to a real "
            "random value to decouple OAuth-state signing from the "
            "cron/admin/internal/Telegram secret."
        )
        _oauth_state_secret_warned = True
    return FUNCTION_SECRET


def _mint_state(
    auth_user_id: str, origin_url: str = "", redirect_path: str = "/dashboard/integrations",
    mode: str = "primary", extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    jti = uuid.uuid4().hex
    exp_ts = int(time.time()) + 600
    payload = {
        "sub": auth_user_id,
        "jti": jti,
        "exp": exp_ts,
        "path": redirect_path,
        "mode": mode,
    }
    if origin_url:
        payload["origin"] = origin_url
    if extra_claims:
        payload.update(extra_claims)
    # Record the nonce as issued-but-unconsumed so _decode_state can enforce
    # single-use (reject reuse of a captured state token, e.g. leaked via a
    # Referer header on the OAuth provider's redirect).
    try:
        supabase.table("oauth_state_nonces").insert({
            "jti": jti,
            "auth_user_id": auth_user_id,
            "expires_at": datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat(),
        }).execute()
    except Exception:  # noqa: BLE001
        logger.exception("failed to record oauth_state_nonces row for jti %s", jti)
    return jwt.encode(payload, _oauth_state_secret(), algorithm="HS256")


def _consume_state_nonce(jti: Optional[str]) -> bool:
    """Marks a state-JWT nonce consumed; returns False if it was missing or
    already consumed (replay). Fails OPEN on a database error (logs and
    allows) rather than locking every OAuth flow out if the nonces table is
    briefly unreachable — the JWT signature/exp checks still apply either
    way, this only adds single-use on top."""
    if not jti:
        return False
    try:
        res = (
            supabase.table("oauth_state_nonces")
            .select("consumed_at")
            .eq("jti", jti)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return False
        if res.data.get("consumed_at"):
            return False
        supabase.table("oauth_state_nonces").update({
            "consumed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("jti", jti).execute()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("failed to consume oauth_state_nonces row for jti %s", jti)
        return True


def _decode_state_claim(state: str, key: str) -> Optional[str]:
    """Reads one extra (non-standard) claim out of an OAuth state JWT — used
    for PKCE's code_verifier, which has to survive the redirect round-trip
    statelessly.

    Does NOT consume the nonce (the same state JWT carries both the PKCE
    verifier and the main claims, and _decode_state — called separately for
    the same request — is what enforces single-use; calling this a second
    time for the same request must not itself count as a replay)."""
    try:
        return jwt.decode(state, _oauth_state_secret(), algorithms=["HS256"]).get(key)
    except jwt.PyJWTError:
        return None


def _decode_state(state: str) -> tuple[Optional[str], str, str, str]:
    """Decode OAuth state JWT. Returns (auth_user_id, frontend_url, redirect_path, mode).

    Enforces single-use via the jti claim / oauth_state_nonces table — a
    state JWT that was never minted by _mint_state (no matching nonce row)
    or that has already been consumed is rejected the same as an invalid
    signature."""
    try:
        claims = jwt.decode(state, _oauth_state_secret(), algorithms=["HS256"])
        if not _consume_state_nonce(claims.get("jti")):
            return None, FRONTEND_URL, "/dashboard/integrations", "primary"
        origin = claims.get("origin", "").rstrip("/")
        # Validate origin is an allowed frontend to prevent open-redirect
        if origin and origin not in ALLOWED_ORIGINS:
            origin = ""
        frontend = origin or FRONTEND_URL
        redirect_path = claims.get("path", "/dashboard/integrations")
        return claims["sub"], frontend, redirect_path, claims.get("mode", "primary")
    except jwt.PyJWTError:
        return None, FRONTEND_URL, "/dashboard/integrations", "primary"


# Pro/Executive can connect this many EXTRA Google accounts on top of their
# primary one (real version of the old "up to 3 connected accounts" claim —
# see kin_connected_accounts migration + agent_tools._read_gmail/_read_calendar).
MAX_EXTRA_GOOGLE_ACCOUNTS: dict[str, int] = {"pro": 2, "executive": 2}




# ---------------------------------------------------------------------------
# Usage / quota
# ---------------------------------------------------------------------------


def get_monthly_token_usage(user_id: str) -> dict[str, int]:
    """Real token spend this month, as opposed to the message-count quota
    proxy — closes the audit finding that quotas measured a proxy, not
    actual Gemini cost.

    Sums in Postgres via the kin_monthly_token_usage() RPC (migration
    20260831010000) rather than pulling every message row of the month over
    PostgREST and summing in Python — that was the concrete cause of a slow
    usage/token-count UI for any user with meaningful message volume."""
    try:
        res = supabase.rpc(
            "kin_monthly_token_usage",
            {"p_user_id": user_id, "p_since": _month_start_iso()},
        ).execute()
        row = (res.data or [{}])[0]
        return {
            "prompt_tokens": row.get("prompt_tokens") or 0,
            "completion_tokens": row.get("completion_tokens") or 0,
            "total_tokens": row.get("total_tokens") or 0,
        }
    except Exception:  # noqa: BLE001
        logger.exception("token usage sum failed")
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}




# ---------------------------------------------------------------------------
# Executive-tier features: API keys, webhooks, account manager, prompt tuning.
#
# Added 2026-07-20 to close a gap found in that day's pricing audit: these
# three items were advertised on the Executive billing page with nothing
# enforcing or implementing them anywhere in the backend.
# ---------------------------------------------------------------------------

EXECUTIVE_ONLY = {"executive"}


def _require_executive(user: dict[str, Any]) -> None:
    if plan_for(user) not in EXECUTIVE_ONLY:
        raise HTTPException(
            status_code=403,
            detail="This feature is part of the Executive plan. Upgrade at /dashboard/billing.",
        )


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()



async def _dispatch_kin_webhooks(user_id: str, event: str, data: dict[str, Any]) -> None:
    """Single-attempt delivery, logged for visibility — not a durable retry
    queue (see the migration note in 20260720030000_kin_executive_features.sql).
    Never raises: this runs fire-and-forget from _finalize and must not affect
    the chat reply either way."""
    try:
        res = (
            supabase.table("kin_webhooks")
            .select("id, url, events, secret")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        hooks = [h for h in (res.data or []) if event in (h.get("events") or [])]
        if not hooks:
            return
        payload = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(payload).encode()
        for hook in hooks:
            signature = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
            status, code, err = "failed", None, None
            try:
                # Re-validate at delivery time, not just at create_kin_webhook
                # save time — the URL could resolve somewhere new by now.
                from app.core.url_safety import assert_safe_url
                assert_safe_url(hook["url"])
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(
                        hook["url"],
                        content=body,
                        headers={
                            "Content-Type": "application/json",
                            "X-Kin-Signature": f"sha256={signature}",
                            "X-Kin-Event": event,
                        },
                    )
                code = r.status_code
                status = "delivered" if r.status_code < 300 else "failed"
            except Exception as exc:  # noqa: BLE001
                err = str(exc)[:500]
            supabase.table("kin_webhook_deliveries").insert({
                "webhook_id": hook["id"], "event": event, "payload": payload,
                "status": status, "response_code": code, "last_error": err,
                "delivered_at": datetime.now(timezone.utc).isoformat() if status == "delivered" else None,
            }).execute()
    except Exception:  # noqa: BLE001
        logger.exception("kin webhook dispatch failed for user %s event %s", user_id, event)








# ---------------------------------------------------------------------------
# Long-term memory — list + delete + wipe
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Microsoft 365 — OAuth flow + integration endpoints
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Documents — Drive RAG
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
from cryptography.fernet import Fernet


def _credentials_fernet() -> Fernet:
    key = os.environ.get("BYOK_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("BYOK_ENCRYPTION_KEY not configured")
    return Fernet(key.encode())


def _decode_credentials_payload(encrypted_payload: Any) -> dict[str, Any]:
    if isinstance(encrypted_payload, memoryview):
        encrypted_payload = encrypted_payload.tobytes()
    elif isinstance(encrypted_payload, str) and encrypted_payload.startswith("\\x"):
        encrypted_payload = bytes.fromhex(encrypted_payload[2:])
    plaintext = _credentials_fernet().decrypt(encrypted_payload)
    return json.loads(plaintext.decode())


# ---------------------------------------------------------------------------
# MCP Server Management Endpoints
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Scheduled Tasks Management Endpoints
# ---------------------------------------------------------------------------



async def send_scheduled_task_email(user: dict[str, Any], subject: str, markdown_content: str) -> dict[str, Any]:
    # Convert markdown to basic HTML for email styling
    import re
    html = markdown_content
    
    # Headers
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold & Italic
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Code blocks
    html = re.sub(r'```(.*?)\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
    
    # Lists
    lines = html.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                new_lines.append('<ul>')
                in_list = True
            content = stripped[2:]
            new_lines.append(f'  <li>{content}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    html = '\n'.join(new_lines)
    
    # Paragraphs (empty lines separate paragraphs)
    paragraphs = html.split('\n\n')
    formatted_paragraphs = []
    for p in paragraphs:
        p_stripped = p.strip()
        if not p_stripped:
            continue
        if p_stripped.startswith('<h') or p_stripped.startswith('<ul') or p_stripped.startswith('<ol') or p_stripped.startswith('<pre') or p_stripped.startswith('<li'):
            formatted_paragraphs.append(p_stripped)
        else:
            p_formatted = p_stripped.replace('\n', '<br>')
            formatted_paragraphs.append(f'<p>{p_formatted}</p>')
            
    html = '\n'.join(formatted_paragraphs)
    
    # Premium layout styling
    premium_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                color: #1a1a1a;
                line-height: 1.6;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #fafafa;
            }}
            .container {{
                background-color: #ffffff;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
                border: 1px solid #e5e7eb;
            }}
            h1, h2, h3 {{
                color: #111827;
                font-weight: 700;
                margin-top: 24px;
                margin-bottom: 12px;
            }}
            h1 {{ font-size: 24px; border-bottom: 2px solid #f3f4f6; padding-bottom: 8px; }}
            h2 {{ font-size: 20px; }}
            h3 {{ font-size: 16px; }}
            p {{
                margin-top: 0;
                margin-bottom: 16px;
            }}
            ul {{
                margin-top: 0;
                margin-bottom: 16px;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 8px;
            }}
            code {{
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 0.9em;
                background-color: #f3f4f6;
                padding: 2px 6px;
                border-radius: 4px;
                color: #db2777;
            }}
            pre {{
                background-color: #f3f4f6;
                padding: 16px;
                border-radius: 8px;
                overflow-x: auto;
                margin-top: 0;
                margin-bottom: 16px;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
                border-radius: 0;
                color: #1f2937;
            }}
            .footer {{
                margin-top: 32px;
                font-size: 12px;
                color: #6b7280;
                text-align: center;
                border-top: 1px solid #f3f4f6;
                padding-top: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {html}
            <div class="footer">
                Sent automatically by your personal assistant Kin.
            </div>
        </div>
    </body>
    </html>
    """
    
    google_sent = False
    outlook_sent = False
    
    if user.get("google_refresh_token"):
        try:
            import google_integrations as g
            await g.send_gmail(
                supabase=supabase,
                user=user,
                to=[user["email"]],
                subject=subject,
                body=premium_html,
                html=True
            )
            google_sent = True
            logger.info("Successfully sent scheduled task email via Gmail to %s", user["email"])
        except Exception:
            logger.exception("Failed to send scheduled task email via Gmail")
            
    if not google_sent and user.get("microsoft_refresh_token"):
        try:
            import microsoft_integrations as ms
            await ms.send_outlook_message(
                supabase=supabase,
                user=user,
                to=[user["email"]],
                subject=subject,
                body=premium_html,
                html=True
            )
            outlook_sent = True
            logger.info("Successfully sent scheduled task email via Outlook to %s", user["email"])
        except Exception:
            logger.exception("Failed to send scheduled task email via Outlook")
            
    if google_sent or outlook_sent:
        return {"status": "success", "channel": "gmail" if google_sent else "outlook"}
    else:
        raise Exception("Neither Gmail nor Outlook email integrations are linked or valid.")


async def send_onesignal_notification(user_id: str, title: str, message: str) -> bool:
    onesignal_app_id = os.environ.get("ONESIGNAL_APP_ID")
    onesignal_key = os.environ.get("ONESIGNAL_REST_API_KEY")
    if not onesignal_app_id or not onesignal_key:
        logger.info("OneSignal not configured. Skipping web push notification.")
        return False
    
    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Authorization": f"Basic {onesignal_key}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "app_id": onesignal_app_id,
        "include_external_user_ids": [user_id],
        "headings": {"en": title},
        "contents": {"en": message},
    }
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            logger.info("OneSignal response: %s", r.text)
            return r.status_code == 200
    except Exception:
        logger.exception("Failed to send OneSignal push notification")
        return False




# ---------------------------------------------------------------------------
# Routers (imported at the bottom to avoid circular-import ordering issues —
# these router modules bridge back into main.py via `from main import X` for
# helpers/constants defined earlier in this file's execution order).
# ---------------------------------------------------------------------------
from app.routers import account_manager  # noqa: E402
from app.routers import billing_webhooks  # noqa: E402
from app.routers import chat  # noqa: E402
from app.routers import documents  # noqa: E402
from app.routers import email_triggers  # noqa: E402
from app.routers import kin_webhooks  # noqa: E402
from app.routers import llm_keys  # noqa: E402
from app.routers import marketplace  # noqa: E402
from app.routers import mcp  # noqa: E402
from app.routers import memory  # noqa: E402
from app.routers import personal_integrations  # noqa: E402
from app.routers import prompt_tuning  # noqa: E402
from app.routers import public_api  # noqa: E402
from app.routers import schedule  # noqa: E402
from app.routers import settings  # noqa: E402
from app.routers import social  # noqa: E402
from app.routers import voice_agents  # noqa: E402

app.include_router(account_manager.router)
app.include_router(billing_webhooks.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(email_triggers.router)
app.include_router(kin_webhooks.router)
app.include_router(llm_keys.router)
app.include_router(marketplace.router)
app.include_router(mcp.router)
app.include_router(memory.router)
app.include_router(personal_integrations.router)
app.include_router(prompt_tuning.router)
app.include_router(public_api.router)
app.include_router(schedule.router)
app.include_router(settings.router)
app.include_router(social.router)
app.include_router(voice_agents.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
