-- Expand the built-in 'ai' integration so the node drawer exposes
-- provider / model / system prompt fields. Default values keep behavior
-- backwards-compatible (Kin's Gemini 2.5 Flash, no extra setup).
--
-- For non-Kin providers (openai / anthropic / groq / cohere), the dispatcher
-- looks up the stored credentials of the matching dedicated integration
-- (openai_text / anthropic_claude / groq / cohere) — so the user only has
-- to add the API key once via the marketplace flow.

UPDATE integrations SET manifest = '{
  "auth":{"type":"none","_note":"Kin default uses Gemini via your project. To use OpenAI / Anthropic / Groq / Cohere, install the matching marketplace integration first to store your API key."},
  "actions":[
    {
      "name":"summarize",
      "label":"Summarize text",
      "inputs":[
        {"name":"input","type":"string","required":true,"help":"Text to summarize"},
        {"name":"style","type":"string","default":"bullet","help":"bullet, paragraph, headline, or exec-summary"},
        {"name":"provider","type":"string","default":"kin","help":"kin (default Gemini) | openai | anthropic | groq | cohere"},
        {"name":"model","type":"string","help":"Override the default model for this provider. Leave empty for the sensible default."},
        {"name":"system","type":"string","help":"Optional system prompt"}
      ],
      "outputs":[{"name":"text","type":"string"}]
    },
    {
      "name":"classify",
      "label":"Classify into a category",
      "inputs":[
        {"name":"input","type":"string","required":true,"help":"Text to classify"},
        {"name":"categories","type":"array","required":true,"help":"List of allowed categories"},
        {"name":"provider","type":"string","default":"kin"},
        {"name":"model","type":"string"},
        {"name":"system","type":"string","help":"Optional extra instructions"}
      ],
      "outputs":[{"name":"category","type":"string"},{"name":"confidence","type":"number"}]
    },
    {
      "name":"extract_json",
      "label":"Extract structured JSON from text",
      "inputs":[
        {"name":"input","type":"string","required":true,"help":"Raw text"},
        {"name":"schema","type":"object","required":true,"help":"JSON schema describing fields to extract"},
        {"name":"provider","type":"string","default":"kin"},
        {"name":"model","type":"string"},
        {"name":"system","type":"string"}
      ],
      "outputs":[{"name":"result","type":"object"}]
    },
    {
      "name":"generate",
      "label":"Generate text from a prompt",
      "inputs":[
        {"name":"prompt","type":"string","required":true,"help":"What to generate"},
        {"name":"system","type":"string","help":"Optional system instructions"},
        {"name":"provider","type":"string","default":"kin","help":"kin | openai | anthropic | groq | cohere"},
        {"name":"model","type":"string","help":"Override default model"},
        {"name":"temperature","type":"number","default":0.4,"help":"0 = deterministic, 1 = creative"}
      ],
      "outputs":[{"name":"text","type":"string"}]
    },
    {
      "name":"chat",
      "label":"Multi-turn chat (returns assistant reply)",
      "inputs":[
        {"name":"messages","type":"array","required":true,"help":"Array of {role, content} objects"},
        {"name":"system","type":"string"},
        {"name":"provider","type":"string","default":"kin"},
        {"name":"model","type":"string"}
      ],
      "outputs":[{"name":"text","type":"string"}]
    }
  ]
}'::jsonb WHERE slug = 'ai';
