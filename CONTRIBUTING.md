# Contributing to Kin

Thanks for your interest in contributing. Kin is a monorepo with three
services — pick the one you're working on and follow its setup below.

## Repo layout

```
kin/
├── backend/       FastAPI — chat/tool-calling agent, RAG, integrations, billing
├── frontend/      Next.js — dashboard and chat UI
├── voice-worker/  LiveKit Agents — phone/voice-call handling
└── docker-compose.yml
```

## Development setup

**Backend:**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in a Supabase project + GEMINI_API_KEY at minimum
uvicorn main:app --reload --port 8080
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

**Voice worker** (optional — only needed if you're working on voice/phone-call
features):

```bash
cd voice-worker
pip install -r requirements.txt
cp .env.example .env
python worker.py dev
```

Or bring everything up at once with Docker Compose — see the root
[README](README.md#quick-start-docker-compose).

## Running tests

```bash
cd backend && pytest tests/ -q
```

The frontend and voice-worker don't have test suites yet — that's a known
gap and a good area for a first contribution.

CI runs a compile/lint/build check for all three services on every push/PR
against `main`.

## Code style

Match the existing patterns in the file you're editing rather than imposing
a different style. Keep pull requests focused: avoid mixing unrelated
reformatting, renames, or import-sorting into a functional change — those
make diffs hard to review and hard to revert independently. If you spot
something worth cleaning up separately, call it out and send it as its own
PR.

## LLM calls: use `backend/app/core/llm.py`

The backend is mid-migration to a unified, LiteLLM-based LLM layer living in
`backend/app/core/llm.py`, giving consistent fallback behavior, per-request
cost tracking, and multi-provider support across Gemini, OpenAI, Anthropic,
and OpenRouter. If you're adding any new code that calls out to an LLM,
please build on `app/core/llm.py` rather than adding another direct
`google-genai`, `openai`, or `anthropic` SDK call.

## Pull requests

- Keep PRs small and focused on one change, in one service where possible.
- Add or update tests for any new backend behavior or bug fix.
- Describe what changed and why in the PR description; link any related
  issue.
- Be prepared to iterate based on review feedback — this is a fast-moving,
  production-backing codebase, so changes touching shared infrastructure
  (auth, billing, config loading) get a closer look.
