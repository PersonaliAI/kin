-- More built-in integrations — all driven by the generic manifest HTTP
-- executor, so no Python handlers required. The shape matches the YAML
-- example in the publish-form docs: `request: { method, url, headers, body }`
-- with `{{ auth.X }}` and `{{ input.Y }}` placeholders, plus a
-- `response_map: { out_name: $.json.path }` for shaping the output.

INSERT INTO integrations (slug, name, description, category, source, status, publisher_name, manifest, icon_url) VALUES

('github', 'GitHub — Create Issue', 'Create issues in a GitHub repo.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth": {"type": "api_key",
     "fields": [{"name": "token", "label": "Personal Access Token",
                  "help": "Get at github.com/settings/tokens — needs `repo` scope."}]},
   "actions": [{
     "name": "create_issue",
     "inputs": [{"name":"owner","type":"string","required":true},
                 {"name":"repo","type":"string","required":true},
                 {"name":"title","type":"string","required":true},
                 {"name":"body","type":"string"}],
     "outputs": [{"name":"number","type":"int"},{"name":"url","type":"string"}],
     "request": {
       "method": "POST",
       "url":    "https://api.github.com/repos/{{ input.owner }}/{{ input.repo }}/issues",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Accept":"application/vnd.github+json"},
       "body":   "{\"title\":\"{{ input.title }}\",\"body\":\"{{ input.body }}\"}"
     },
     "response_map":{"number":"$.number","url":"$.html_url"}
   }]
 }'::jsonb, '/icons/github.svg'),

('github_dispatch', 'GitHub — Trigger Workflow', 'Fire a workflow_dispatch event for a GitHub Actions workflow.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth": {"type":"api_key","fields":[{"name":"token","label":"Personal Access Token"}]},
   "actions":[{
     "name":"dispatch",
     "inputs":[{"name":"owner","type":"string","required":true},
                {"name":"repo","type":"string","required":true},
                {"name":"workflow","type":"string","required":true,"help":"workflow file name e.g. ci.yml"},
                {"name":"ref","type":"string","required":true,"help":"branch e.g. main"}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST",
       "url":"https://api.github.com/repos/{{ input.owner }}/{{ input.repo }}/actions/workflows/{{ input.workflow }}/dispatches",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Accept":"application/vnd.github+json"},
       "body":"{\"ref\":\"{{ input.ref }}\"}"
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb, '/icons/github.svg'),

('stripe_refund', 'Stripe — Refund Charge', 'Refund a Stripe charge by id.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"secret_key","label":"Stripe Secret Key","help":"sk_live_... or sk_test_..."}]},
   "actions":[{
     "name":"refund_charge",
     "inputs":[{"name":"charge","type":"string","required":true},
                {"name":"amount","type":"int","help":"Optional — partial refund in cents"}],
     "outputs":[{"name":"id","type":"string"},{"name":"status","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.stripe.com/v1/refunds?charge={{ input.charge }}",
       "headers":{"Authorization":"Bearer {{ auth.secret_key }}","Content-Type":"application/x-www-form-urlencoded"}
     },
     "response_map":{"id":"$.id","status":"$.status"}
   }]
 }'::jsonb, '/icons/stripe.svg'),

('hubspot', 'HubSpot — Create Contact', 'Create or update a HubSpot contact.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Private App Token","help":"hubspot.com/settings → Integrations → Private Apps"}]},
   "actions":[{
     "name":"create_contact",
     "inputs":[{"name":"email","type":"string","required":true},
                {"name":"firstname","type":"string"},
                {"name":"lastname","type":"string"},
                {"name":"company","type":"string"}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.hubapi.com/crm/v3/objects/contacts",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"properties\":{\"email\":\"{{ input.email }}\",\"firstname\":\"{{ input.firstname }}\",\"lastname\":\"{{ input.lastname }}\",\"company\":\"{{ input.company }}\"}}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb, '/icons/hubspot.svg'),

('zoom', 'Zoom — Create Meeting', 'Schedule a Zoom meeting.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"access_token","label":"OAuth Access Token","help":"Generate via your Zoom OAuth app"}]},
   "actions":[{
     "name":"create_meeting",
     "inputs":[{"name":"topic","type":"string","required":true},
                {"name":"start_time","type":"string","required":true,"help":"ISO 8601 UTC"},
                {"name":"duration","type":"int","default":30}],
     "outputs":[{"name":"join_url","type":"string"},{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.zoom.us/v2/users/me/meetings",
       "headers":{"Authorization":"Bearer {{ auth.access_token }}","Content-Type":"application/json"},
       "body":"{\"topic\":\"{{ input.topic }}\",\"type\":2,\"start_time\":\"{{ input.start_time }}\",\"duration\":{{ input.duration }},\"timezone\":\"UTC\"}"
     },
     "response_map":{"join_url":"$.join_url","id":"$.id"}
   }]
 }'::jsonb, '/icons/zoom.svg'),

('calendly', 'Calendly — List Scheduled Events', 'Pull scheduled events from Calendly.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Personal Access Token","help":"calendly.com/integrations/api_webhooks"}]},
   "actions":[{
     "name":"list_events",
     "inputs":[{"name":"user_uri","type":"string","required":true,"help":"Calendly user URI"}],
     "outputs":[{"name":"events","type":"array"}],
     "request":{
       "method":"GET",
       "url":"https://api.calendly.com/scheduled_events?user={{ input.user_uri }}",
       "headers":{"Authorization":"Bearer {{ auth.token }}"}
     },
     "response_map":{"events":"$.collection"}
   }]
 }'::jsonb, '/icons/calendly.svg'),

('typeform', 'Typeform — Get Responses', 'Fetch recent responses from a Typeform.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Personal Token","help":"admin.typeform.com/account#/section/tokens"}]},
   "actions":[{
     "name":"list_responses",
     "inputs":[{"name":"form_id","type":"string","required":true},
                {"name":"page_size","type":"int","default":25}],
     "outputs":[{"name":"items","type":"array"}],
     "request":{
       "method":"GET",
       "url":"https://api.typeform.com/forms/{{ input.form_id }}/responses?page_size={{ input.page_size }}",
       "headers":{"Authorization":"Bearer {{ auth.token }}"}
     },
     "response_map":{"items":"$.items"}
   }]
 }'::jsonb, '/icons/typeform.svg'),

('clickup', 'ClickUp — Create Task', 'Create a task in a ClickUp list.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Personal API Key"}]},
   "actions":[{
     "name":"create_task",
     "inputs":[{"name":"list_id","type":"string","required":true},
                {"name":"name","type":"string","required":true},
                {"name":"description","type":"string"}],
     "outputs":[{"name":"id","type":"string"},{"name":"url","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.clickup.com/api/v2/list/{{ input.list_id }}/task",
       "headers":{"Authorization":"{{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"name\":\"{{ input.name }}\",\"description\":\"{{ input.description }}\"}"
     },
     "response_map":{"id":"$.id","url":"$.url"}
   }]
 }'::jsonb, '/icons/clickup.svg'),

('asana', 'Asana — Create Task', 'Create a task in Asana.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Personal Access Token"}]},
   "actions":[{
     "name":"create_task",
     "inputs":[{"name":"project","type":"string","required":true},
                {"name":"name","type":"string","required":true},
                {"name":"notes","type":"string"}],
     "outputs":[{"name":"gid","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://app.asana.com/api/1.0/tasks",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"data\":{\"projects\":[\"{{ input.project }}\"],\"name\":\"{{ input.name }}\",\"notes\":\"{{ input.notes }}\"}}"
     },
     "response_map":{"gid":"$.data.gid"}
   }]
 }'::jsonb, '/icons/asana.svg'),

('jira', 'Jira — Create Issue', 'Create an issue in Jira Cloud.', 'productivity', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"email","label":"Atlassian email"},
     {"name":"token","label":"API Token","help":"id.atlassian.com/manage-profile/security/api-tokens"},
     {"name":"site","label":"Site URL","help":"e.g. yourorg.atlassian.net"}]},
   "actions":[{
     "name":"create_issue",
     "inputs":[{"name":"project_key","type":"string","required":true},
                {"name":"summary","type":"string","required":true},
                {"name":"issuetype","type":"string","default":"Task"}],
     "outputs":[{"name":"key","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://{{ auth.site }}/rest/api/3/issue",
       "headers":{"Authorization":"Basic {{ auth.email }}:{{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"fields\":{\"project\":{\"key\":\"{{ input.project_key }}\"},\"summary\":\"{{ input.summary }}\",\"issuetype\":{\"name\":\"{{ input.issuetype }}\"}}}"
     },
     "response_map":{"key":"$.key"}
   }]
 }'::jsonb, '/icons/jira.svg'),

('intercom', 'Intercom — Send Message', 'Send a message to a user in Intercom.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"Access Token"}]},
   "actions":[{
     "name":"send_message",
     "inputs":[{"name":"user_id","type":"string","required":true},
                {"name":"body","type":"string","required":true}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.intercom.io/messages",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Content-Type":"application/json","Accept":"application/json"},
       "body":"{\"message_type\":\"inapp\",\"body\":\"{{ input.body }}\",\"from\":{\"type\":\"admin\",\"id\":\"0\"},\"to\":{\"type\":\"user\",\"id\":\"{{ input.user_id }}\"}}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb, '/icons/intercom.svg'),

('mailchimp', 'Mailchimp — Add Subscriber', 'Add a member to a Mailchimp audience.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"api_key","label":"API Key","help":"Format: abcd1234-us21 (the dc suffix is required)"},
     {"name":"dc","label":"Data Center","help":"From your API key, e.g. us21"}]},
   "actions":[{
     "name":"add_subscriber",
     "inputs":[{"name":"list_id","type":"string","required":true},
                {"name":"email","type":"string","required":true},
                {"name":"status","type":"string","default":"subscribed"}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://{{ auth.dc }}.api.mailchimp.com/3.0/lists/{{ input.list_id }}/members",
       "headers":{"Authorization":"apikey {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"email_address\":\"{{ input.email }}\",\"status\":\"{{ input.status }}\"}"
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb, '/icons/mailchimp.svg'),

('sendgrid', 'SendGrid — Send Email', 'Send transactional email via SendGrid.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"api_key","label":"API Key"},
     {"name":"from_email","label":"Verified sender email"}]},
   "actions":[{
     "name":"send_email",
     "inputs":[{"name":"to","type":"string","required":true},
                {"name":"subject","type":"string","required":true},
                {"name":"text","type":"string","required":true}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"POST",
       "url":"https://api.sendgrid.com/v3/mail/send",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"personalizations\":[{\"to\":[{\"email\":\"{{ input.to }}\"}]}],\"from\":{\"email\":\"{{ auth.from_email }}\"},\"subject\":\"{{ input.subject }}\",\"content\":[{\"type\":\"text/plain\",\"value\":\"{{ input.text }}\"}]}"
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb, '/icons/sendgrid.svg'),

('mailgun', 'Mailgun — Send Email', 'Send email via Mailgun.', 'communication', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"api_key","label":"Private API Key"},
     {"name":"domain","label":"Mailgun Domain"},
     {"name":"from_email","label":"From email"}]},
   "actions":[{
     "name":"send_email",
     "inputs":[{"name":"to","type":"string","required":true},
                {"name":"subject","type":"string","required":true},
                {"name":"text","type":"string","required":true}],
     "outputs":[{"name":"id","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.mailgun.net/v3/{{ auth.domain }}/messages",
       "headers":{"Authorization":"Basic api:{{ auth.api_key }}","Content-Type":"application/x-www-form-urlencoded"}
     },
     "response_map":{"id":"$.id"}
   }]
 }'::jsonb, '/icons/mailgun.svg'),

('openai_image', 'OpenAI — Generate Image', 'Generate an image with OpenAI DALL·E.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"OpenAI API Key"}]},
   "actions":[{
     "name":"generate_image",
     "inputs":[{"name":"prompt","type":"string","required":true},
                {"name":"size","type":"string","default":"1024x1024"}],
     "outputs":[{"name":"url","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.openai.com/v1/images/generations",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}","Content-Type":"application/json"},
       "body":"{\"model\":\"dall-e-3\",\"prompt\":\"{{ input.prompt }}\",\"size\":\"{{ input.size }}\",\"n\":1}"
     },
     "response_map":{"url":"$.data[0].url"}
   }]
 }'::jsonb, '/icons/openai.svg'),

('replicate', 'Replicate — Run Model', 'Run any model on Replicate.', 'ai', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"token","label":"API Token"}]},
   "actions":[{
     "name":"run_model",
     "inputs":[{"name":"version","type":"string","required":true,"help":"Model version hash"},
                {"name":"input","type":"object","required":true}],
     "outputs":[{"name":"id","type":"string"},{"name":"status","type":"string"}],
     "request":{
       "method":"POST",
       "url":"https://api.replicate.com/v1/predictions",
       "headers":{"Authorization":"Bearer {{ auth.token }}","Content-Type":"application/json"},
       "body":"{\"version\":\"{{ input.version }}\",\"input\":{{ input.input }}}"
     },
     "response_map":{"id":"$.id","status":"$.status"}
   }]
 }'::jsonb, '/icons/replicate.svg'),

('s3_put', 'AWS S3 — Public Upload via Presigned URL', 'Upload bytes via a pre-generated S3 presigned URL.', 'storage', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"upload",
     "inputs":[{"name":"url","type":"string","required":true,"help":"Pre-signed PUT URL"},
                {"name":"content","type":"string","required":true,"help":"String to upload"},
                {"name":"content_type","type":"string","default":"text/plain"}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"PUT",
       "url":"{{ input.url }}",
       "headers":{"Content-Type":"{{ input.content_type }}"},
       "body":"{{ input.content }}"
     },
     "response_map":{"ok":"$"}
   }]
 }'::jsonb, '/icons/s3.svg'),

('cloudflare_kv', 'Cloudflare KV — Put Value', 'Write a value into a Cloudflare Workers KV namespace.', 'storage', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"account_id","label":"Cloudflare Account ID"},
     {"name":"namespace_id","label":"KV Namespace ID"},
     {"name":"api_token","label":"API Token"}]},
   "actions":[{
     "name":"put",
     "inputs":[{"name":"key","type":"string","required":true},
                {"name":"value","type":"string","required":true}],
     "outputs":[{"name":"ok","type":"boolean"}],
     "request":{
       "method":"PUT",
       "url":"https://api.cloudflare.com/client/v4/accounts/{{ auth.account_id }}/storage/kv/namespaces/{{ auth.namespace_id }}/values/{{ input.key }}",
       "headers":{"Authorization":"Bearer {{ auth.api_token }}","Content-Type":"text/plain"},
       "body":"{{ input.value }}"
     },
     "response_map":{"ok":"$.success"}
   }]
 }'::jsonb, '/icons/cloudflare.svg'),

('shopify_order', 'Shopify — List Recent Orders', 'List recent orders from a Shopify store.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[
     {"name":"shop","label":"Shop subdomain","help":"e.g. mystore (without .myshopify.com)"},
     {"name":"token","label":"Admin API Access Token"}]},
   "actions":[{
     "name":"list_orders",
     "inputs":[{"name":"limit","type":"int","default":25}],
     "outputs":[{"name":"orders","type":"array"}],
     "request":{
       "method":"GET",
       "url":"https://{{ auth.shop }}.myshopify.com/admin/api/2024-01/orders.json?limit={{ input.limit }}",
       "headers":{"X-Shopify-Access-Token":"{{ auth.token }}"}
     },
     "response_map":{"orders":"$.orders"}
   }]
 }'::jsonb, '/icons/shopify.svg'),

('clearbit', 'Clearbit — Enrich Email', 'Enrich a person by email address.', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"api_key","fields":[{"name":"api_key","label":"API Key"}]},
   "actions":[{
     "name":"enrich",
     "inputs":[{"name":"email","type":"string","required":true}],
     "outputs":[{"name":"person","type":"object"},{"name":"company","type":"object"}],
     "request":{
       "method":"GET",
       "url":"https://person.clearbit.com/v2/combined/find?email={{ input.email }}",
       "headers":{"Authorization":"Bearer {{ auth.api_key }}"}
     },
     "response_map":{"person":"$.person","company":"$.company"}
   }]
 }'::jsonb, '/icons/clearbit.svg'),

('weather', 'Open-Meteo — Weather', 'Free weather forecast (no auth required).', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"forecast",
     "inputs":[{"name":"latitude","type":"number","required":true},
                {"name":"longitude","type":"number","required":true}],
     "outputs":[{"name":"current","type":"object"}],
     "request":{
       "method":"GET",
       "url":"https://api.open-meteo.com/v1/forecast?latitude={{ input.latitude }}&longitude={{ input.longitude }}&current=temperature_2m,wind_speed_10m,weather_code"
     },
     "response_map":{"current":"$.current"}
   }]
 }'::jsonb, '/icons/weather.svg'),

('exchange_rate', 'Currency — Exchange Rate', 'Convert one currency to another (free).', 'data', 'community', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"convert",
     "inputs":[{"name":"from","type":"string","required":true},
                {"name":"to","type":"string","required":true},
                {"name":"amount","type":"number","default":1}],
     "outputs":[{"name":"rate","type":"number"},{"name":"converted","type":"number"}],
     "request":{
       "method":"GET",
       "url":"https://api.exchangerate.host/convert?from={{ input.from }}&to={{ input.to }}&amount={{ input.amount }}"
     },
     "response_map":{"rate":"$.info.rate","converted":"$.result"}
   }]
 }'::jsonb, '/icons/currency.svg'),

('code_js', 'Code — JavaScript', 'Run a snippet of JavaScript in a sandbox. Input is `inputs`, return the value you want as output.', 'data', 'builtin', 'published', 'Kin',
 '{
   "auth":{"type":"none"},
   "actions":[{
     "name":"run",
     "inputs":[{"name":"code","type":"string","required":true,"help":"JS expression / function body. Use `inputs` for context."},
                {"name":"inputs","type":"object","help":"Variables exposed as `inputs` in the JS scope."}],
     "outputs":[{"name":"value","type":"any"}]
   }]
 }'::jsonb, '/icons/code.svg')

ON CONFLICT (slug) DO UPDATE
  SET name        = EXCLUDED.name,
      description = EXCLUDED.description,
      category    = EXCLUDED.category,
      manifest    = EXCLUDED.manifest,
      icon_url    = EXCLUDED.icon_url,
      updated_at  = NOW();
