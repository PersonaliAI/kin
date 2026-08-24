-- 60 more integrations — researched from n8n's nodes-base for action shape,
-- re-implemented in our own manifest format (HTTP request + JSONPath response
-- mapping). All call public APIs directly; no n8n code copied.
--
-- All entries are 'community' source and 'published' status so they show in
-- the marketplace immediately.

INSERT INTO integrations (slug, name, description, category, source, status, publisher_name, manifest, icon_url) VALUES

-- ============ AI / LLM ============
('anthropic_claude', 'Anthropic — Claude', 'Generate text with Claude (Sonnet, Opus, Haiku).', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Anthropic API Key","help":"Get at console.anthropic.com"}]},
   "actions":[{
     "name":"complete",
     "label":"Complete a prompt",
     "inputs":[{"name":"prompt","type":"string","required":true},
                {"name":"system","type":"string","help":"Optional system prompt"},
                {"name":"model","type":"string","default":"claude-sonnet-4-20250514"},
                {"name":"max_tokens","type":"int","default":2048}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.anthropic.com/v1/messages",
       "headers":{"x-api-key":"{{ auth.api_key }}","anthropic-version":"2023-06-01","content-type":"application/json"},
       "body":"{\"model\":\"{{ input.model }}\",\"max_tokens\":{{ input.max_tokens }},\"system\":\"{{ input.system }}\",\"messages\":[{\"role\":\"user\",\"content\":\"{{ input.prompt }}\"}]}"
     },
     "response_map":{"text":"$.content[0].text"}
   }]
 }'::jsonb,'/icons/anthropic.svg'),

('openai_text', 'OpenAI — Chat Completion', 'Generate text with GPT-4o or GPT-5.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"OpenAI API Key"}]},
   "actions":[{
     "name":"complete",
     "inputs":[{"name":"prompt","type":"string","required":true},
                {"name":"system","type":"string"},
                {"name":"model","type":"string","default":"gpt-4o-mini"}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.openai.com/v1/chat/completions",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"model\":\"{{ input.model }}\",\"messages\":[{\"role\":\"system\",\"content\":\"{{ input.system }}\"},{\"role\":\"user\",\"content\":\"{{ input.prompt }}\"}]}"
     },
     "response_map":{"text":"$.choices[0].message.content"}
   }]
 }'::jsonb,'/icons/openai.svg'),

('perplexity', 'Perplexity — Online Search', 'Web-grounded LLM answers via Perplexity.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Perplexity API Key"}]},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"query","type":"string","required":true},
                {"name":"model","type":"string","default":"llama-3.1-sonar-small-128k-online"}],
     "outputs":[{"name":"text","type":"string"},{"name":"citations","type":"array"}],
     "request":{
       "method":"POST","url":"https://api.perplexity.ai/chat/completions",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"model\":\"{{ input.model }}\",\"messages\":[{\"role\":\"user\",\"content\":\"{{ input.query }}\"}]}"
     },
     "response_map":{"text":"$.choices[0].message.content","citations":"$.citations"}
   }]
 }'::jsonb,'/icons/perplexity.svg'),

('groq', 'Groq — Fast Inference', 'Super-fast LLM inference via Groq.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Groq API Key"}]},
   "actions":[{
     "name":"complete",
     "inputs":[{"name":"prompt","type":"string","required":true},
                {"name":"model","type":"string","default":"llama-3.3-70b-versatile"}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.groq.com/openai/v1/chat/completions",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"model\":\"{{ input.model }}\",\"messages\":[{\"role\":\"user\",\"content\":\"{{ input.prompt }}\"}]}"
     },
     "response_map":{"text":"$.choices[0].message.content"}
   }]
 }'::jsonb,'/icons/groq.svg'),

('cohere', 'Cohere — Generate', 'Text generation via Cohere.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Cohere API Key"}]},
   "actions":[{
     "name":"generate",
     "inputs":[{"name":"message","type":"string","required":true},
                {"name":"model","type":"string","default":"command-r-plus"}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.cohere.com/v2/chat",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"model\":\"{{ input.model }}\",\"messages\":[{\"role\":\"user\",\"content\":\"{{ input.message }}\"}]}"
     },
     "response_map":{"text":"$.message.content[0].text"}
   }]
 }'::jsonb,'/icons/cohere.svg'),

('elevenlabs_tts', 'ElevenLabs — Text to Speech', 'Generate speech audio from text.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"ElevenLabs API Key"},
                                       {"name":"voice_id","label":"Voice ID","help":"From elevenlabs.io/voice-lab"}]},
   "actions":[{
     "name":"synthesize",
     "inputs":[{"name":"text","type":"string","required":true},
                {"name":"model_id","type":"string","default":"eleven_multilingual_v2"}],
     "outputs":[{"name":"audio_base64","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.elevenlabs.io/v1/text-to-speech/{{ auth.voice_id }}",
       "headers":{"xi-api-key":"{{ auth.api_key }}","Content-Type":"application/json","Accept":"audio/mpeg"},
       "body":"{\"text\":\"{{ input.text }}\",\"model_id\":\"{{ input.model_id }}\"}"
     },
     "response_map":{"audio_base64":"$"}
   }]
 }'::jsonb,'/icons/elevenlabs.svg'),

('huggingface', 'Hugging Face — Inference', 'Run any HF Inference API model.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"HF Token","help":"huggingface.co/settings/tokens"}]},
   "actions":[{
     "name":"infer",
     "inputs":[{"name":"model","type":"string","required":true,"help":"e.g. meta-llama/Llama-3-8B"},
                {"name":"inputs","type":"string","required":true}],
     "outputs":[{"name":"result","type":"any"}],
     "request":{
       "method":"POST","url":"https://api-inference.huggingface.co/models/{{ input.model }}",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"inputs\":\"{{ input.inputs }}\"}"
     },
     "response_map":{"result":"$"}
   }]
 }'::jsonb,'/icons/huggingface.svg'),

-- ============ CRM ============
('pipedrive', 'Pipedrive — Create Deal', 'Create a deal in Pipedrive.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"api_token","label":"API Token"},
     {"name":"company_domain","label":"Company Domain","help":"e.g. mycompany"}]},
   "actions":[{
     "name":"create_deal",
     "inputs":[{"name":"title","type":"string","required":true},
                {"name":"value","type":"number"},
                {"name":"currency","type":"string","default":"USD"},
                {"name":"person_id","type":"int"}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST",
       "url":"https://{{ auth.company_domain }}.pipedrive.com/api/v1/deals?api_token={{ auth.api_token }}",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"title\":\"{{ input.title }}\",\"value\":{{ input.value }},\"currency\":\"{{ input.currency }}\",\"person_id\":{{ input.person_id }}}"
     },
     "response_map":{"id":"$.data.id"}
   }]
 }'::jsonb,'/icons/pipedrive.svg'),

('activecampaign', 'ActiveCampaign — Add Contact', 'Add or update a contact.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"api_url","label":"API URL","help":"e.g. https://youraccount.api-us1.com"},
     {"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"add_contact",
     "inputs":[{"name":"email","type":"string","required":true},
                {"name":"first_name","type":"string"},
                {"name":"last_name","type":"string"}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST","url":"{{ auth.api_url }}/api/3/contact/sync",
       "headers":{"Api-Token":"{{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"contact\":{\"email\":\"{{ input.email }}\",\"firstName\":\"{{ input.first_name }}\",\"lastName\":\"{{ input.last_name }}\"}}"
     },
     "response_map":{"id":"$.contact.id"}
   }]
 }'::jsonb,'/icons/activecampaign.svg'),

('brevo', 'Brevo — Send Transactional', 'Send a transactional email via Brevo.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API v3 key"},
                                       {"name":"sender_email","label":"Sender email"},
                                       {"name":"sender_name","label":"Sender name"}]},
   "actions":[{
     "name":"send_email",
     "inputs":[{"name":"to","type":"string","required":true},
                {"name":"subject","type":"string","required":true},
                {"name":"html","type":"string","required":true}],
     "outputs":[{"name":"message_id","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.brevo.com/v3/smtp/email",
       "headers":{"api-key":"{{ auth.api_key }}","Content-Type":"application/json","Accept":"application/json"},
       "body":"{\"sender\":{\"name\":\"{{ auth.sender_name }}\",\"email\":\"{{ auth.sender_email }}\"},\"to\":[{\"email\":\"{{ input.to }}\"}],\"subject\":\"{{ input.subject }}\",\"htmlContent\":\"{{ input.html }}\"}"
     },
     "response_map":{"message_id":"$.messageId"}
   }]
 }'::jsonb,'/icons/brevo.svg'),

('zoho_crm', 'Zoho CRM — Create Lead', 'Create a lead in Zoho CRM.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"access_token","label":"Access Token"},
                                       {"name":"region","label":"Region","help":"e.g. com, eu, in"}]},
   "actions":[{
     "name":"create_lead",
     "inputs":[{"name":"first_name","type":"string"},
                {"name":"last_name","type":"string","required":true},
                {"name":"email","type":"string"},
                {"name":"company","type":"string"}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://www.zohoapis.{{ auth.region }}/crm/v2/Leads",
       "headers":{"Authorization":"Zoho-oauthtoken {{ auth.access_token }}","Content-Type":"application/json"},
       "body":"{\"data\":[{\"Last_Name\":\"{{ input.last_name }}\",\"First_Name\":\"{{ input.first_name }}\",\"Email\":\"{{ input.email }}\",\"Company\":\"{{ input.company }}\"}]}"
     },
     "response_map":{"id":"$.data[0].details.id"}
   }]
 }'::jsonb,'/icons/zoho.svg'),

-- ============ COMMUNICATION ============
('teams_webhook', 'Microsoft Teams — Webhook Card', 'Post a card to a Teams channel via incoming webhook.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"webhook_url","label":"Webhook URL"}]},
   "actions":[{
     "name":"post_card",
     "inputs":[{"name":"title","type":"string","required":true},
                {"name":"text","type":"string","required":true}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST","url":"{{ auth.webhook_url }}",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"type\":\"message\",\"attachments\":[{\"contentType\":\"application/vnd.microsoft.card.adaptive\",\"content\":{\"$schema\":\"http://adaptivecards.io/schemas/adaptive-card.json\",\"version\":\"1.4\",\"type\":\"AdaptiveCard\",\"body\":[{\"type\":\"TextBlock\",\"size\":\"large\",\"weight\":\"bolder\",\"text\":\"{{ input.title }}\"},{\"type\":\"TextBlock\",\"wrap\":true,\"text\":\"{{ input.text }}\"}]}}]}"
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb,'/icons/teams.svg'),

('telegram_send_photo', 'Telegram — Send Photo', 'Send a photo to a Telegram chat.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"bot_token","label":"Bot Token","help":"From @BotFather"}]},
   "actions":[{
     "name":"send_photo",
     "inputs":[{"name":"chat_id","type":"string","required":true},
                {"name":"photo_url","type":"string","required":true},
                {"name":"caption","type":"string"}],
     "outputs":[{"name":"message_id","type":"int"}],
     "request":{
       "method":"POST","url":"https://api.telegram.org/bot{{ auth.bot_token }}/sendPhoto",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"chat_id\":\"{{ input.chat_id }}\",\"photo\":\"{{ input.photo_url }}\",\"caption\":\"{{ input.caption }}\"}"
     },
     "response_map":{"message_id":"$.result.message_id"}
   }]
 }'::jsonb,'/icons/telegram.svg'),

('whatsapp_cloud', 'WhatsApp — Send Message (Cloud API)', 'Send a WhatsApp text message via Meta Cloud API.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"access_token","label":"Access Token"},
     {"name":"phone_number_id","label":"Phone Number ID"}]},
   "actions":[{
     "name":"send_text",
     "inputs":[{"name":"to","type":"string","required":true},
                {"name":"text","type":"string","required":true}],
     "outputs":[{"name":"message_id","type":"string"}],
     "request":{
       "method":"POST","url":"https://graph.facebook.com/v18.0/{{ auth.phone_number_id }}/messages",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Content-Type":"application/json"},
       "body":"{\"messaging_product\":\"whatsapp\",\"to\":\"{{ input.to }}\",\"type\":\"text\",\"text\":{\"body\":\"{{ input.text }}\"}}"
     },
     "response_map":{"message_id":"$.messages[0].id"}
   }]
 }'::jsonb,'/icons/whatsapp.svg'),

('messagebird_sms', 'MessageBird — Send SMS', 'Send an SMS via MessageBird.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"access_key","label":"Access Key"},
                                       {"name":"originator","label":"Originator","help":"phone number or alphanumeric"}]},
   "actions":[{
     "name":"send_sms",
     "inputs":[{"name":"to","type":"string","required":true},
                {"name":"body","type":"string","required":true}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST","url":"https://rest.messagebird.com/messages",
       "headers":{"Authorization":"AccessKey {{ auth.access_key }}","Content-Type":"application/json"},
       "body":"{\"originator\":\"{{ auth.originator }}\",\"recipients\":[\"{{ input.to }}\"],\"body\":\"{{ input.body }}\"}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/messagebird.svg'),

-- ============ STORAGE / FILES ============
('dropbox_upload', 'Dropbox — Upload Text', 'Upload a text file to Dropbox.', 'storage', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"access_token","label":"Access Token"}]},
   "actions":[{
     "name":"upload",
     "inputs":[{"name":"path","type":"string","required":true,"help":"e.g. /reports/2026/q1.txt"},
                {"name":"content","type":"string","required":true}],
     "outputs":[{"name":"path","type":"string"},{"name":"id","type":"string"}],
     "request":{
       "method":"POST","url":"https://content.dropboxapi.com/2/files/upload",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Dropbox-API-Arg":"{\"path\":\"{{ input.path }}\",\"mode\":\"add\",\"autorename\":true}","Content-Type":"application/octet-stream"},
       "body":"{{ input.content }}"
     },
     "response_map":{"path":"$.path_display","id":"$.id"}
   }]
 }'::jsonb,'/icons/dropbox.svg'),

('box_create_folder', 'Box — Create Folder', 'Create a Box folder.', 'storage', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"access_token","label":"Access Token"}]},
   "actions":[{
     "name":"create_folder",
     "inputs":[{"name":"parent_id","type":"string","default":"0"},
                {"name":"name","type":"string","required":true}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.box.com/2.0/folders",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Content-Type":"application/json"},
       "body":"{\"name\":\"{{ input.name }}\",\"parent\":{\"id\":\"{{ input.parent_id }}\"}}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/box.svg'),

-- ============ DEV / OPS ============
('gitlab_issue', 'GitLab — Create Issue', 'Create an issue in a GitLab project.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Personal Access Token"},
                                       {"name":"host","label":"Host","help":"gitlab.com or self-hosted"}]},
   "actions":[{
     "name":"create_issue",
     "inputs":[{"name":"project_id","type":"string","required":true,"help":"URL-encoded path or numeric id"},
                {"name":"title","type":"string","required":true},
                {"name":"description","type":"string"}],
     "outputs":[{"name":"iid","type":"int"},{"name":"web_url","type":"string"}],
     "request":{
       "method":"POST","url":"https://{{ auth.host }}/api/v4/projects/{{ input.project_id }}/issues",
       "headers":{"PRIVATE-TOKEN":"{{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"title\":\"{{ input.title }}\",\"description\":\"{{ input.description }}\"}"
     },
     "response_map":{"iid":"$.iid","web_url":"$.web_url"}
   }]
 }'::jsonb,'/icons/gitlab.svg'),

('bitbucket_pr', 'Bitbucket — Create Pull Request', 'Create a PR in Bitbucket.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"username","label":"Username"},
                                       {"name":"app_password","label":"App Password"}]},
   "actions":[{
     "name":"create_pr",
     "inputs":[{"name":"workspace","type":"string","required":true},
                {"name":"repo","type":"string","required":true},
                {"name":"title","type":"string","required":true},
                {"name":"source","type":"string","required":true,"help":"Source branch"},
                {"name":"destination","type":"string","required":true,"help":"Destination branch"}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST","url":"https://api.bitbucket.org/2.0/repositories/{{ input.workspace }}/{{ input.repo }}/pullrequests",
       "headers":{"Authorization":"Basic {{ auth.username }}:{{ auth.app_password }}","Content-Type":"application/json"},
       "body":"{\"title\":\"{{ input.title }}\",\"source\":{\"branch\":{\"name\":\"{{ input.source }}\"}},\"destination\":{\"branch\":{\"name\":\"{{ input.destination }}\"}}}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/bitbucket.svg'),

('vercel_deploy', 'Vercel — Trigger Deploy', 'Trigger a deployment via deploy hook.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"hook_url","label":"Deploy Hook URL"}]},
   "actions":[{
     "name":"deploy",
     "inputs":[{"name":"ref","type":"string","help":"Branch or ref to deploy"}],
     "outputs":[{"name":"job","type":"object"}],
     "request":{
       "method":"POST","url":"{{ auth.hook_url }}",
       "headers":{"Content-Type":"application/json"}
     },
     "response_map":{"job":"$.job"}
   }]
 }'::jsonb,'/icons/vercel.svg'),

('netlify_deploy', 'Netlify — Trigger Build', 'Trigger a Netlify build via build hook.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"hook_url","label":"Build Hook URL"}]},
   "actions":[{
     "name":"build",
     "inputs":[],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST","url":"{{ auth.hook_url }}",
       "headers":{"Content-Type":"application/json"}
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb,'/icons/netlify.svg'),

-- ============ CUSTOMER SUPPORT ============
('zendesk_ticket', 'Zendesk — Create Ticket', 'Create a support ticket in Zendesk.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"subdomain","label":"Subdomain","help":"e.g. yourcompany"},
     {"name":"email","label":"Login email"},
     {"name":"token","label":"API Token"}]},
   "actions":[{
     "name":"create_ticket",
     "inputs":[{"name":"subject","type":"string","required":true},
                {"name":"description","type":"string","required":true},
                {"name":"requester_email","type":"string"}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST","url":"https://{{ auth.subdomain }}.zendesk.com/api/v2/tickets.json",
       "headers":{"Authorization":"Basic {{ auth.email }}/token:{{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"ticket\":{\"subject\":\"{{ input.subject }}\",\"comment\":{\"body\":\"{{ input.description }}\"},\"requester\":{\"email\":\"{{ input.requester_email }}\"}}}"
     },
     "response_map":{"id":"$.ticket.id"}
   }]
 }'::jsonb,'/icons/zendesk.svg'),

('freshdesk_ticket', 'Freshdesk — Create Ticket', 'Create a Freshdesk ticket.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"domain","label":"Domain","help":"yourcompany.freshdesk.com"},
     {"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"create_ticket",
     "inputs":[{"name":"subject","type":"string","required":true},
                {"name":"description","type":"string","required":true},
                {"name":"email","type":"string","required":true},
                {"name":"priority","type":"int","default":1}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST","url":"https://{{ auth.domain }}/api/v2/tickets",
       "headers":{"Authorization":"Basic {{ auth.api_key }}:X","Content-Type":"application/json"},
       "body":"{\"subject\":\"{{ input.subject }}\",\"description\":\"{{ input.description }}\",\"email\":\"{{ input.email }}\",\"priority\":{{ input.priority }},\"status\":2}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/freshdesk.svg'),

-- ============ E-COMMERCE ============
('stripe_customer', 'Stripe — Create Customer', 'Create a Stripe customer.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"secret_key","label":"Stripe Secret Key"}]},
   "actions":[{
     "name":"create_customer",
     "inputs":[{"name":"email","type":"string","required":true},
                {"name":"name","type":"string"}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.stripe.com/v1/customers?email={{ input.email }}&name={{ input.name }}",
       "headers":{"Authorization":"Bearer {{ auth.secret_key }}"}
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/stripe.svg'),

('stripe_payment_link', 'Stripe — Create Payment Link', 'Create a Stripe payment link for a fixed price.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"secret_key","label":"Stripe Secret Key"}]},
   "actions":[{
     "name":"create_link",
     "inputs":[{"name":"price_id","type":"string","required":true,"help":"e.g. price_123"},
                {"name":"quantity","type":"int","default":1}],
     "outputs":[{"name":"url","type":"string"},{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.stripe.com/v1/payment_links?line_items[0][price]={{ input.price_id }}&line_items[0][quantity]={{ input.quantity }}",
       "headers":{"Authorization":"Bearer {{ auth.secret_key }}"}
     },
     "response_map":{"id":"$.id","url":"$.url"}
   }]
 }'::jsonb,'/icons/stripe.svg'),

('lemon_squeezy', 'Lemon Squeezy — Create Checkout', 'Create a Lemon Squeezy checkout link.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"create_checkout",
     "inputs":[{"name":"store_id","type":"string","required":true},
                {"name":"variant_id","type":"string","required":true}],
     "outputs":[{"name":"url","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.lemonsqueezy.com/v1/checkouts",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/vnd.api+json","Accept":"application/vnd.api+json"},
       "body":"{\"data\":{\"type\":\"checkouts\",\"relationships\":{\"store\":{\"data\":{\"type\":\"stores\",\"id\":\"{{ input.store_id }}\"}},\"variant\":{\"data\":{\"type\":\"variants\",\"id\":\"{{ input.variant_id }}\"}}}}}"
     },
     "response_map":{"url":"$.data.attributes.url"}
   }]
 }'::jsonb,'/icons/lemonsqueezy.svg'),

-- ============ SOCIAL / CONTENT ============
('youtube_search', 'YouTube — Search Videos', 'Search YouTube videos via Data API.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"YouTube Data API Key"}]},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"query","type":"string","required":true},
                {"name":"max_results","type":"int","default":10}],
     "outputs":[{"name":"items","type":"array"}],
     "request":{
       "method":"GET","url":"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={{ input.query }}&maxResults={{ input.max_results }}&key={{ auth.api_key }}"
     },
     "response_map":{"items":"$.items"}
   }]
 }'::jsonb,'/icons/youtube.svg'),

('reddit_post', 'Reddit — Get Subreddit Posts', 'Fetch top posts from a subreddit (public).', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"list_top",
     "inputs":[{"name":"subreddit","type":"string","required":true,"help":"e.g. machinelearning"},
                {"name":"limit","type":"int","default":10}],
     "outputs":[{"name":"posts","type":"array"}],
     "request":{
       "method":"GET","url":"https://www.reddit.com/r/{{ input.subreddit }}/top.json?limit={{ input.limit }}",
       "headers":{"User-Agent":"KinFlow/1.0"}
     },
     "response_map":{"posts":"$.data.children"}
   }]
 }'::jsonb,'/icons/reddit.svg'),

('hackernews', 'Hacker News — Top Stories', 'Fetch HN top stories (public, no auth).', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"top",
     "inputs":[],
     "outputs":[{"name":"ids","type":"array"}],
     "request":{
       "method":"GET","url":"https://hacker-news.firebaseio.com/v0/topstories.json"
     },
     "response_map":{"ids":"$"}
   }]
 }'::jsonb,'/icons/hackernews.svg'),

('webflow_publish', 'Webflow — Publish Site', 'Publish a Webflow site to the live domain.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"API Token"}]},
   "actions":[{
     "name":"publish",
     "inputs":[{"name":"site_id","type":"string","required":true},
                {"name":"domains","type":"array","help":"List of domain ids"}],
     "outputs":[{"name":"queued","type":"boolean"}],
     "request":{
       "method":"POST","url":"https://api.webflow.com/v2/sites/{{ input.site_id }}/publish",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"customDomains\":{{ input.domains }}}"
     },
     "response_map":{"queued":"$.queued"}
   }]
 }'::jsonb,'/icons/webflow.svg'),

-- ============ MARKETING / ANALYTICS ============
('mixpanel_track', 'Mixpanel — Track Event', 'Send an event to Mixpanel.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"project_token","label":"Project Token"}]},
   "actions":[{
     "name":"track",
     "inputs":[{"name":"event","type":"string","required":true},
                {"name":"distinct_id","type":"string","required":true},
                {"name":"properties","type":"object"}],
     "outputs":[{"name":"ok","type":"int"}],
     "request":{
       "method":"POST","url":"https://api.mixpanel.com/track",
       "headers":{"Content-Type":"application/x-www-form-urlencoded","Accept":"text/plain"}
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb,'/icons/mixpanel.svg'),

('posthog_capture', 'PostHog — Capture Event', 'Send an event to PostHog.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Project API Key"},
                                       {"name":"host","label":"Host","help":"e.g. https://app.posthog.com"}]},
   "actions":[{
     "name":"capture",
     "inputs":[{"name":"event","type":"string","required":true},
                {"name":"distinct_id","type":"string","required":true},
                {"name":"properties","type":"object"}],
     "outputs":[{"name":"status","type":"int"}],
     "request":{
       "method":"POST","url":"{{ auth.host }}/capture/",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"api_key\":\"{{ auth.api_key }}\",\"event\":\"{{ input.event }}\",\"distinct_id\":\"{{ input.distinct_id }}\",\"properties\":{{ input.properties }}}"
     },
     "response_map":{"status":"$.status"}
   }]
 }'::jsonb,'/icons/posthog.svg'),

('segment_track', 'Segment — Track Event', 'Send an event to Segment.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"write_key","label":"Write Key"}]},
   "actions":[{
     "name":"track",
     "inputs":[{"name":"user_id","type":"string","required":true},
                {"name":"event","type":"string","required":true},
                {"name":"properties","type":"object"}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST","url":"https://api.segment.io/v1/track",
       "headers":{"Authorization":"Basic {{ auth.write_key }}:","Content-Type":"application/json"},
       "body":"{\"userId\":\"{{ input.user_id }}\",\"event\":\"{{ input.event }}\",\"properties\":{{ input.properties }}}"
     },
     "response_map":{"ok":"$.success"}
   }]
 }'::jsonb,'/icons/segment.svg'),

('plausible', 'Plausible — Send Event', 'Track an event in Plausible Analytics.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"domain","label":"Domain","help":"e.g. mysite.com"}]},
   "actions":[{
     "name":"event",
     "inputs":[{"name":"name","type":"string","required":true},
                {"name":"url","type":"string","required":true}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST","url":"https://plausible.io/api/event",
       "headers":{"Content-Type":"application/json","User-Agent":"KinFlow/1.0"},
       "body":"{\"domain\":\"{{ auth.domain }}\",\"name\":\"{{ input.name }}\",\"url\":\"{{ input.url }}\"}"
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb,'/icons/plausible.svg'),

-- ============ FILES / DOCS ============
('pdf_co', 'PDF.co — HTML to PDF', 'Convert HTML to a PDF URL.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"html_to_pdf",
     "inputs":[{"name":"html","type":"string","required":true}],
     "outputs":[{"name":"url","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.pdf.co/v1/pdf/convert/from/html",
       "headers":{"x-api-key":"{{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"html\":\"{{ input.html }}\",\"async\":false}"
     },
     "response_map":{"url":"$.url"}
   }]
 }'::jsonb,'/icons/pdfco.svg'),

('docusign_send', 'DocuSign — Send Envelope', 'Send a DocuSign envelope.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"access_token","label":"Access Token"},
     {"name":"account_id","label":"Account ID"},
     {"name":"base_uri","label":"Base URI","help":"e.g. https://demo.docusign.net"}]},
   "actions":[{
     "name":"send_envelope",
     "inputs":[{"name":"template_id","type":"string","required":true},
                {"name":"signer_email","type":"string","required":true},
                {"name":"signer_name","type":"string","required":true}],
     "outputs":[{"name":"envelope_id","type":"string"}],
     "request":{
       "method":"POST","url":"{{ auth.base_uri }}/restapi/v2.1/accounts/{{ auth.account_id }}/envelopes",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Content-Type":"application/json"},
       "body":"{\"templateId\":\"{{ input.template_id }}\",\"templateRoles\":[{\"email\":\"{{ input.signer_email }}\",\"name\":\"{{ input.signer_name }}\",\"roleName\":\"signer\"}],\"status\":\"sent\"}"
     },
     "response_map":{"envelope_id":"$.envelopeId"}
   }]
 }'::jsonb,'/icons/docusign.svg'),

-- ============ DATA / WEB ============
('rss_fetch', 'RSS — Fetch Feed', 'Fetch and parse an RSS / Atom feed.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"fetch",
     "inputs":[{"name":"url","type":"string","required":true}],
     "outputs":[{"name":"items","type":"array"}],
     "request":{
       "method":"GET","url":"https://api.rss2json.com/v1/api.json?rss_url={{ input.url }}"
     },
     "response_map":{"items":"$.items"}
   }]
 }'::jsonb,'/icons/rss.svg'),

('scrape_url', 'Scrape — Get HTML', 'Fetch the raw HTML of any URL.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"get",
     "inputs":[{"name":"url","type":"string","required":true}],
     "outputs":[{"name":"html","type":"string"}],
     "request":{
       "method":"GET","url":"{{ input.url }}",
       "headers":{"User-Agent":"Mozilla/5.0 KinFlow/1.0"}
     },
     "response_map":{"html":"$"}
   }]
 }'::jsonb,'/icons/scrape.svg'),

('jsonbin', 'JSONBin — Read Bin', 'Read a JSONBin.io storage bin.', 'storage', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"master_key","label":"Master Key"}]},
   "actions":[{
     "name":"read",
     "inputs":[{"name":"bin_id","type":"string","required":true}],
     "outputs":[{"name":"record","type":"any"}],
     "request":{
       "method":"GET","url":"https://api.jsonbin.io/v3/b/{{ input.bin_id }}/latest",
       "headers":{"X-Master-Key":"{{ auth.master_key }}"}
     },
     "response_map":{"record":"$.record"}
   }]
 }'::jsonb,'/icons/jsonbin.svg'),

-- ============ SEARCH / SCHEDULING ============
('cal_com_event', 'Cal.com — Create Event Type', 'Create an event type on Cal.com.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"create_event_type",
     "inputs":[{"name":"title","type":"string","required":true},
                {"name":"slug","type":"string","required":true},
                {"name":"length","type":"int","default":30}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST","url":"https://api.cal.com/v1/event-types?apiKey={{ auth.api_key }}",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"title\":\"{{ input.title }}\",\"slug\":\"{{ input.slug }}\",\"length\":{{ input.length }}}"
     },
     "response_map":{"id":"$.event_type.id"}
   }]
 }'::jsonb,'/icons/calcom.svg'),

('serpapi', 'SerpAPI — Google Search', 'Run a Google search via SerpAPI.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"q","type":"string","required":true},
                {"name":"engine","type":"string","default":"google"}],
     "outputs":[{"name":"organic_results","type":"array"}],
     "request":{
       "method":"GET","url":"https://serpapi.com/search?q={{ input.q }}&engine={{ input.engine }}&api_key={{ auth.api_key }}"
     },
     "response_map":{"organic_results":"$.organic_results"}
   }]
 }'::jsonb,'/icons/serpapi.svg'),

('brave_search', 'Brave Search — Web', 'Search the web via Brave Search API.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Subscription Token"}]},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"q","type":"string","required":true}],
     "outputs":[{"name":"web","type":"object"}],
     "request":{
       "method":"GET","url":"https://api.search.brave.com/res/v1/web/search?q={{ input.q }}",
       "headers":{"X-Subscription-Token":"{{ auth.token }}","Accept":"application/json"}
     },
     "response_map":{"web":"$.web"}
   }]
 }'::jsonb,'/icons/brave.svg'),

-- ============ PROJECT MGMT ============
('monday_create_item', 'Monday.com — Create Item', 'Create an item in a Monday board.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"API Token"}]},
   "actions":[{
     "name":"create_item",
     "inputs":[{"name":"board_id","type":"int","required":true},
                {"name":"item_name","type":"string","required":true}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST","url":"https://api.monday.com/v2",
       "headers":{"Authorization":"{{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"query\":\"mutation { create_item (board_id: {{ input.board_id }}, item_name: \\\"{{ input.item_name }}\\\") { id } }\"}"
     },
     "response_map":{"id":"$.data.create_item.id"}
   }]
 }'::jsonb,'/icons/monday.svg'),

('basecamp_message', 'Basecamp — Post Message', 'Post a message to a Basecamp project.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"access_token","label":"Access Token"},
     {"name":"account_id","label":"Account ID"}]},
   "actions":[{
     "name":"post_message",
     "inputs":[{"name":"project_id","type":"string","required":true},
                {"name":"board_id","type":"string","required":true},
                {"name":"subject","type":"string","required":true},
                {"name":"content","type":"string","required":true}],
     "outputs":[{"name":"id","type":"int"}],
     "request":{
       "method":"POST","url":"https://3.basecampapi.com/{{ auth.account_id }}/buckets/{{ input.project_id }}/message_boards/{{ input.board_id }}/messages.json",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Content-Type":"application/json","User-Agent":"KinFlow"},
       "body":"{\"subject\":\"{{ input.subject }}\",\"content\":\"{{ input.content }}\",\"status\":\"active\"}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb,'/icons/basecamp.svg'),

-- ============ MISC API HELPERS ============
('discord_dm', 'Discord — Create DM', 'Create a DM channel with a user (then send a message via Discord Webhook).', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"bot_token","label":"Bot Token"}]},
   "actions":[{
     "name":"create_dm",
     "inputs":[{"name":"recipient_id","type":"string","required":true}],
     "outputs":[{"name":"channel_id","type":"string"}],
     "request":{
       "method":"POST","url":"https://discord.com/api/v10/users/@me/channels",
       "headers":{"Authorization":"Bot {{ auth.bot_token }}","Content-Type":"application/json"},
       "body":"{\"recipient_id\":\"{{ input.recipient_id }}\"}"
     },
     "response_map":{"channel_id":"$.id"}
   }]
 }'::jsonb,'/icons/discord.svg'),

('ip_info', 'IP Info — Lookup IP', 'Get geographic info for an IP address.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Token"}]},
   "actions":[{
     "name":"lookup",
     "inputs":[{"name":"ip","type":"string","required":true}],
     "outputs":[{"name":"city","type":"string"},{"name":"country","type":"string"},{"name":"org","type":"string"}],
     "request":{
       "method":"GET","url":"https://ipinfo.io/{{ input.ip }}/json?token={{ auth.token }}"
     },
     "response_map":{"city":"$.city","country":"$.country","org":"$.org"}
   }]
 }'::jsonb,'/icons/ipinfo.svg'),

('translate_deepl', 'DeepL — Translate', 'Translate text via DeepL.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"},
                                       {"name":"plan","label":"Plan","help":"free or pro"}]},
   "actions":[{
     "name":"translate",
     "inputs":[{"name":"text","type":"string","required":true},
                {"name":"target_lang","type":"string","required":true,"help":"e.g. EN, DE, ES"}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://api-{{ auth.plan }}.deepl.com/v2/translate",
       "headers":{"Authorization":"DeepL-Auth-Key {{ auth.api_key }}","Content-Type":"application/x-www-form-urlencoded"}
     },
     "response_map":{"text":"$.translations[0].text"}
   }]
 }'::jsonb,'/icons/deepl.svg'),

('googletrans', 'Google Translate — Translate', 'Translate text via Google Translation API.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"Google API Key"}]},
   "actions":[{
     "name":"translate",
     "inputs":[{"name":"q","type":"string","required":true},
                {"name":"target","type":"string","required":true,"help":"ISO code, e.g. en, fr"}],
     "outputs":[{"name":"text","type":"string"}],
     "request":{
       "method":"POST","url":"https://translation.googleapis.com/language/translate/v2?key={{ auth.api_key }}",
       "headers":{"Content-Type":"application/json"},
       "body":"{\"q\":\"{{ input.q }}\",\"target\":\"{{ input.target }}\"}"
     },
     "response_map":{"text":"$.data.translations[0].translatedText"}
   }]
 }'::jsonb,'/icons/gtranslate.svg'),

('crisp_message', 'Crisp — Send Message', 'Send a message to a Crisp conversation.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"identifier","label":"Identifier"},
     {"name":"key","label":"Key"},
     {"name":"website_id","label":"Website ID"}]},
   "actions":[{
     "name":"send_message",
     "inputs":[{"name":"session_id","type":"string","required":true},
                {"name":"content","type":"string","required":true}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST","url":"https://api.crisp.chat/v1/website/{{ auth.website_id }}/conversation/{{ input.session_id }}/message",
       "headers":{"Authorization":"Basic {{ auth.identifier }}:{{ auth.key }}","Content-Type":"application/json","X-Crisp-Tier":"plugin"},
       "body":"{\"type\":\"text\",\"from\":\"operator\",\"origin\":\"chat\",\"content\":\"{{ input.content }}\"}"
     },
     "response_map":{"ok":"$.error"}
   }]
 }'::jsonb,'/icons/crisp.svg'),

-- ============ COMMUNITY / FUN ============
('giphy_search', 'Giphy — Search GIFs', 'Search Giphy for a GIF URL.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"q","type":"string","required":true},
                {"name":"limit","type":"int","default":5}],
     "outputs":[{"name":"gifs","type":"array"}],
     "request":{
       "method":"GET","url":"https://api.giphy.com/v1/gifs/search?api_key={{ auth.api_key }}&q={{ input.q }}&limit={{ input.limit }}"
     },
     "response_map":{"gifs":"$.data"}
   }]
 }'::jsonb,'/icons/giphy.svg'),

('open_library', 'Open Library — Search Books', 'Search books on Open Library (public).', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"search",
     "inputs":[{"name":"q","type":"string","required":true}],
     "outputs":[{"name":"docs","type":"array"}],
     "request":{
       "method":"GET","url":"https://openlibrary.org/search.json?q={{ input.q }}"
     },
     "response_map":{"docs":"$.docs"}
   }]
 }'::jsonb,'/icons/openlibrary.svg'),

('news_api', 'NewsAPI — Top Headlines', 'Fetch top headlines from NewsAPI.org.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"top_headlines",
     "inputs":[{"name":"country","type":"string","default":"us"},
                {"name":"category","type":"string","help":"business, entertainment, sports, technology…"}],
     "outputs":[{"name":"articles","type":"array"}],
     "request":{
       "method":"GET","url":"https://newsapi.org/v2/top-headlines?country={{ input.country }}&category={{ input.category }}&apiKey={{ auth.api_key }}"
     },
     "response_map":{"articles":"$.articles"}
   }]
 }'::jsonb,'/icons/news.svg')

ON CONFLICT (slug) DO UPDATE
  SET name        = EXCLUDED.name,
      description = EXCLUDED.description,
      category    = EXCLUDED.category,
      manifest    = EXCLUDED.manifest,
      icon_url    = EXCLUDED.icon_url,
      updated_at  = NOW();
