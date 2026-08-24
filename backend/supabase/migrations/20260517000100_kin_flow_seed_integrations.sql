-- Seed the built-in integration catalog. These are the integrations Kin Flow
-- ships with on day one — no community involvement required. Built-ins reuse
-- the existing PersonaliAI OAuth tokens (Google, Microsoft) so users don't
-- have to re-authenticate.
--
-- Manifest schema:
--   {
--     "auth":  { "type": "oauth_passthrough" | "api_key" | "none",
--                "provider": "google" | "microsoft",
--                "fields": [{name, label, help}] },
--     "actions":  [{ name, label, description, inputs:[...], outputs:[...] }],
--     "triggers": [{ name, label, description, config_schema }]
--   }
--
-- Built-ins have `source = 'builtin'` and `publisher_user_id = NULL`.
-- They are immediately published and don't require install before use.

INSERT INTO integrations (slug, name, description, category, source, status, publisher_name, manifest, icon_url)
VALUES
  -- ============ TRIGGERS ============
  ('trigger.cron', 'Schedule (Cron)', 'Run a flow on a schedule.', 'trigger', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "triggers": [{
       "name": "scheduled",
       "label": "On schedule",
       "config_schema": {"expr": "cron expression", "tz": "IANA timezone"}
     }]
   }'::jsonb, '/icons/cron.svg'),

  ('trigger.webhook', 'Webhook', 'Receive HTTP POST requests as a trigger.', 'trigger', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "triggers": [{
       "name": "on_request",
       "label": "On HTTP POST",
       "config_schema": {"method": "POST"}
     }]
   }'::jsonb, '/icons/webhook.svg'),

  ('trigger.manual', 'Manual run', 'Trigger the flow from the dashboard or chat.', 'trigger', 'builtin', 'published', 'Kin',
   '{"auth": {"type": "none"}, "triggers": [{"name": "manual", "label": "Manual"}]}'::jsonb,
   '/icons/manual.svg'),

  -- ============ COMMUNICATION ============
  ('gmail', 'Gmail', 'Send, read, and reply to Gmail messages.', 'communication', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "google"},
     "actions": [
       {"name": "list_messages", "label": "List messages",
        "inputs": [{"name": "query", "type": "string", "default": "is:unread"},
                   {"name": "limit", "type": "int",    "default": 25}],
        "outputs": [{"name": "messages", "type": "array"}]},
       {"name": "send_email", "label": "Send email",
        "inputs": [{"name": "to", "type": "string", "required": true},
                   {"name": "subject", "type": "string", "required": true},
                   {"name": "body", "type": "string", "required": true}],
        "outputs": [{"name": "message_id", "type": "string"}]},
       {"name": "reply_email", "label": "Reply to email",
        "inputs": [{"name": "message_id", "type": "string", "required": true},
                   {"name": "body", "type": "string", "required": true}],
        "outputs": [{"name": "thread_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/gmail.svg'),

  ('outlook', 'Outlook Mail', 'Send and read Microsoft Outlook emails.', 'communication', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "microsoft"},
     "actions": [
       {"name": "list_messages",
        "inputs": [{"name": "query", "type": "string"},
                   {"name": "max_days_old", "type": "int"},
                   {"name": "limit", "type": "int", "default": 25}],
        "outputs": [{"name": "messages", "type": "array"}]},
       {"name": "send_email",
        "inputs": [{"name": "to", "type": "string", "required": true},
                   {"name": "subject", "type": "string", "required": true},
                   {"name": "body", "type": "string", "required": true}],
        "outputs": [{"name": "ok", "type": "boolean"}]}
     ]
   }'::jsonb, '/icons/outlook.svg'),

  ('slack', 'Slack', 'Post messages to Slack channels or DMs.', 'communication', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "bot_token", "label": "Bot User OAuth Token",
                          "help": "Get from api.slack.com → Your App → OAuth & Permissions. Starts with xoxb-..."}]},
     "actions": [
       {"name": "post_message",
        "inputs": [{"name": "channel", "type": "string", "required": true,
                    "help": "#channel-name, channel id, or @user"},
                   {"name": "text", "type": "string", "required": true}],
        "outputs": [{"name": "ts", "type": "string"}]}
     ]
   }'::jsonb, '/icons/slack.svg'),

  ('discord', 'Discord', 'Post messages to Discord channels via a webhook URL.', 'communication', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "webhook_url", "label": "Discord Webhook URL"}]},
     "actions": [
       {"name": "post_message",
        "inputs": [{"name": "text", "type": "string", "required": true},
                   {"name": "username", "type": "string"}],
        "outputs": [{"name": "ok", "type": "boolean"}]}
     ]
   }'::jsonb, '/icons/discord.svg'),

  ('telegram', 'Telegram', 'Send messages from your linked Telegram chat with Kin.', 'communication', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "telegram"},
     "actions": [
       {"name": "send_message",
        "inputs": [{"name": "text", "type": "string", "required": true}],
        "outputs": [{"name": "ok", "type": "boolean"}]}
     ]
   }'::jsonb, '/icons/telegram.svg'),

  ('twilio_sms', 'Twilio SMS', 'Send SMS messages globally.', 'communication', 'community', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "account_sid", "label": "Account SID"},
                         {"name": "auth_token",  "label": "Auth Token"},
                         {"name": "from_number", "label": "From phone number (E.164)"}]},
     "actions": [
       {"name": "send_sms",
        "inputs": [{"name": "to", "type": "string", "required": true},
                   {"name": "body", "type": "string", "required": true}],
        "outputs": [{"name": "sid", "type": "string"}]}
     ]
   }'::jsonb, '/icons/twilio.svg'),

  -- ============ CALENDAR / TASKS / PRODUCTIVITY ============
  ('google_calendar', 'Google Calendar', 'Create, list, and manage Google Calendar events.', 'productivity', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "google"},
     "actions": [
       {"name": "list_events",
        "inputs": [{"name": "days_ahead", "type": "int", "default": 7}],
        "outputs": [{"name": "events", "type": "array"}]},
       {"name": "create_event",
        "inputs": [{"name": "summary", "type": "string", "required": true},
                   {"name": "start", "type": "string", "required": true, "help": "ISO 8601"},
                   {"name": "end", "type": "string", "required": true},
                   {"name": "attendees", "type": "array"},
                   {"name": "description", "type": "string"}],
        "outputs": [{"name": "event_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/gcal.svg'),

  ('outlook_calendar', 'Outlook Calendar', 'Create and read Microsoft Outlook calendar events.', 'productivity', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "microsoft"},
     "actions": [
       {"name": "list_events",
        "inputs": [{"name": "days_ahead", "type": "int", "default": 7}],
        "outputs": [{"name": "events", "type": "array"}]},
       {"name": "create_event",
        "inputs": [{"name": "subject", "type": "string", "required": true},
                   {"name": "start", "type": "string", "required": true},
                   {"name": "end", "type": "string", "required": true},
                   {"name": "attendees", "type": "array"}],
        "outputs": [{"name": "event_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/outlook-cal.svg'),

  ('google_sheets', 'Google Sheets', 'Read and append rows to Google Sheets.', 'productivity', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "google"},
     "actions": [
       {"name": "read_range",
        "inputs": [{"name": "spreadsheet_id", "type": "string", "required": true},
                   {"name": "range", "type": "string", "default": "A1:Z100"}],
        "outputs": [{"name": "values", "type": "array"}]},
       {"name": "append_row",
        "inputs": [{"name": "spreadsheet_id", "type": "string", "required": true},
                   {"name": "range", "type": "string", "default": "A1"},
                   {"name": "values", "type": "array", "required": true}],
        "outputs": [{"name": "ok", "type": "boolean"}]}
     ]
   }'::jsonb, '/icons/sheets.svg'),

  ('notion', 'Notion', 'Create pages and append blocks in Notion.', 'productivity', 'community', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "integration_token", "label": "Internal Integration Token",
                          "help": "Get from notion.so/my-integrations"}]},
     "actions": [
       {"name": "create_page",
        "inputs": [{"name": "parent_database_id", "type": "string", "required": true},
                   {"name": "title", "type": "string", "required": true},
                   {"name": "properties", "type": "object"}],
        "outputs": [{"name": "page_id", "type": "string"},
                    {"name": "url", "type": "string"}]},
       {"name": "append_text",
        "inputs": [{"name": "page_id", "type": "string", "required": true},
                   {"name": "text", "type": "string", "required": true}],
        "outputs": [{"name": "ok", "type": "boolean"}]}
     ]
   }'::jsonb, '/icons/notion.svg'),

  ('airtable', 'Airtable', 'Create and update Airtable records.', 'productivity', 'community', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "api_key", "label": "Personal Access Token",
                          "help": "Get from airtable.com/create/tokens"}]},
     "actions": [
       {"name": "create_record",
        "inputs": [{"name": "base_id", "type": "string", "required": true},
                   {"name": "table", "type": "string", "required": true},
                   {"name": "fields", "type": "object", "required": true}],
        "outputs": [{"name": "record_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/airtable.svg'),

  ('linear', 'Linear', 'Create issues in Linear.', 'productivity', 'community', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "api_key", "label": "Personal API Key",
                          "help": "Get from linear.app/settings/api"}]},
     "actions": [
       {"name": "create_issue",
        "inputs": [{"name": "team_id", "type": "string", "required": true},
                   {"name": "title",   "type": "string", "required": true},
                   {"name": "description", "type": "string"}],
        "outputs": [{"name": "issue_id", "type": "string"},
                    {"name": "url", "type": "string"}]}
     ]
   }'::jsonb, '/icons/linear.svg'),

  ('trello', 'Trello', 'Create cards in Trello boards.', 'productivity', 'community', 'published', 'Kin',
   '{
     "auth": {"type": "api_key",
              "fields": [{"name": "api_key", "label": "API Key", "help": "Get from trello.com/app-key"},
                         {"name": "token",   "label": "Token"}]},
     "actions": [
       {"name": "create_card",
        "inputs": [{"name": "list_id", "type": "string", "required": true},
                   {"name": "name",    "type": "string", "required": true},
                   {"name": "desc",    "type": "string"}],
        "outputs": [{"name": "card_id", "type": "string"},
                    {"name": "url", "type": "string"}]}
     ]
   }'::jsonb, '/icons/trello.svg'),

  ('google_tasks', 'Google Tasks', 'Create Google Tasks.', 'productivity', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "google"},
     "actions": [
       {"name": "create_task",
        "inputs": [{"name": "title", "type": "string", "required": true},
                   {"name": "notes", "type": "string"},
                   {"name": "due",   "type": "string"}],
        "outputs": [{"name": "task_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/gtasks.svg'),

  ('microsoft_todo', 'Microsoft ToDo', 'Create Microsoft ToDo tasks.', 'productivity', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "microsoft"},
     "actions": [
       {"name": "create_task",
        "inputs": [{"name": "list_id", "type": "string"},
                   {"name": "title",   "type": "string", "required": true},
                   {"name": "notes",   "type": "string"}],
        "outputs": [{"name": "task_id", "type": "string"}]}
     ]
   }'::jsonb, '/icons/mstodo.svg'),

  -- ============ AI / DATA / LOGIC ============
  ('ai', 'AI (Gemini)', 'Summarize, classify, extract, or generate with Gemini.', 'ai', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "actions": [
       {"name": "summarize",
        "inputs": [{"name": "input", "type": "string", "required": true},
                   {"name": "style", "type": "string", "default": "bullet"}],
        "outputs": [{"name": "text", "type": "string"}]},
       {"name": "classify",
        "inputs": [{"name": "input", "type": "string", "required": true},
                   {"name": "categories", "type": "array", "required": true}],
        "outputs": [{"name": "category", "type": "string"},
                    {"name": "confidence", "type": "number"}]},
       {"name": "extract_json",
        "inputs": [{"name": "input", "type": "string", "required": true},
                   {"name": "schema", "type": "object", "required": true,
                    "help": "JSON schema describing fields to extract"}],
        "outputs": [{"name": "result", "type": "object"}]},
       {"name": "generate",
        "inputs": [{"name": "prompt", "type": "string", "required": true},
                   {"name": "system", "type": "string"}],
        "outputs": [{"name": "text", "type": "string"}]}
     ]
   }'::jsonb, '/icons/ai.svg'),

  ('http', 'HTTP Request', 'Call any REST API. Universal escape hatch.', 'data', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "actions": [
       {"name": "request",
        "inputs": [{"name": "method", "type": "string", "default": "GET"},
                   {"name": "url",    "type": "string", "required": true},
                   {"name": "headers","type": "object"},
                   {"name": "body",   "type": "object"}],
        "outputs": [{"name": "status", "type": "int"},
                    {"name": "body",   "type": "any"}]}
     ]
   }'::jsonb, '/icons/http.svg'),

  ('transform', 'Transform', 'Map, filter, or reshape data without code.', 'data', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "actions": [
       {"name": "map_fields",
        "inputs": [{"name": "input", "type": "any", "required": true},
                   {"name": "mapping", "type": "object", "required": true,
                    "help": "{new_field: \"{{input.path}}\"}"}],
        "outputs": [{"name": "output", "type": "object"}]},
       {"name": "filter_array",
        "inputs": [{"name": "input", "type": "array", "required": true},
                   {"name": "condition", "type": "string", "required": true,
                    "help": "JS expression returning boolean, e.g. item.unread === true"}],
        "outputs": [{"name": "output", "type": "array"}]}
     ]
   }'::jsonb, '/icons/transform.svg'),

  ('logic', 'Logic', 'Branches, loops, delays, conditions.', 'data', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "none"},
     "actions": [
       {"name": "if",
        "inputs": [{"name": "condition", "type": "string", "required": true,
                    "help": "JS expression, e.g. {{n1.messages.length}} > 0"}],
        "outputs": [{"name": "result", "type": "boolean"}]},
       {"name": "delay",
        "inputs": [{"name": "seconds", "type": "int", "required": true}],
        "outputs": [{"name": "ok", "type": "boolean"}]},
       {"name": "loop",
        "inputs": [{"name": "items", "type": "array", "required": true}],
        "outputs": [{"name": "current", "type": "any"},
                    {"name": "index",   "type": "int"}]}
     ]
   }'::jsonb, '/icons/logic.svg'),

  -- ============ STORAGE ============
  ('google_drive', 'Google Drive', 'Upload and download Drive files.', 'storage', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "google"},
     "actions": [
       {"name": "upload_text",
        "inputs": [{"name": "filename", "type": "string", "required": true},
                   {"name": "text",     "type": "string", "required": true},
                   {"name": "parent_folder_id", "type": "string"}],
        "outputs": [{"name": "file_id", "type": "string"},
                    {"name": "url",     "type": "string"}]}
     ]
   }'::jsonb, '/icons/drive.svg'),

  ('onedrive', 'OneDrive', 'Upload and download OneDrive files.', 'storage', 'builtin', 'published', 'Kin',
   '{
     "auth": {"type": "oauth_passthrough", "provider": "microsoft"},
     "actions": [
       {"name": "upload_text",
        "inputs": [{"name": "filename", "type": "string", "required": true},
                   {"name": "text",     "type": "string", "required": true},
                   {"name": "parent_folder_id", "type": "string"}],
        "outputs": [{"name": "file_id", "type": "string"},
                    {"name": "url",     "type": "string"}]}
     ]
   }'::jsonb, '/icons/onedrive.svg')

ON CONFLICT (slug) DO UPDATE
  SET name = EXCLUDED.name,
      description = EXCLUDED.description,
      category = EXCLUDED.category,
      manifest = EXCLUDED.manifest,
      icon_url = EXCLUDED.icon_url,
      updated_at = NOW();
