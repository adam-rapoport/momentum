# pMomentum

An AI assistant for product management work — drafts PRDs, stakeholder updates,
and meeting prep docs through guided skill workflows, with persistent memory
across sessions and Google Docs integration for deliverables.

Built as an MVP by a solo non-technical PM with Claude Code as the pair
programmer. Still in active development.

## Stack

- **Backend:** FastAPI (Python 3.12) + SQLAlchemy + asyncpg + Redis
- **Frontend:** Next.js 15 + TypeScript + Tailwind + Zustand
- **LLM providers:** Groq (`llama-4-scout` default) for casual chat and
  tool-heavy turns, Google AI Studio (`gemma-4-31b-it`) for drafting turns.
  Routing is per-turn based on slash commands and active skill state.
- **Services:** Postgres 16 + Redis via Homebrew (not Docker yet)
- **Integrations:** Google Docs (OAuth), Tavily (web search)

## Prerequisites

- macOS (other platforms untested)
- Python 3.12+
- Node.js 18+
- Homebrew with `postgresql@16` and `redis` services
- API keys for:
  - [Groq](https://console.groq.com/keys) — required
  - [Google AI Studio](https://aistudio.google.com/app/apikey) — required for heavy-model drafting
  - [Tavily](https://tavily.com/) — required for WebSearch tool
  - Google Cloud OAuth credentials — required for Google Docs integration

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/adam-rapoport/pmomentum.git
cd pmomentum

# Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

### 2. Start services

```bash
brew services start postgresql@16
brew services start redis
createdb pmomentum
```

### 3. Configure environment

```bash
cd backend
cp .env.example .env
# Edit .env and fill in your API keys + a Fernet key:
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output as CREDENTIAL_VAULT_KEY in .env
```

### 4. Run database migrations and seed

```bash
# From backend/
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed
```

### 5. Start the app

Two terminals:

```bash
# Backend
cd backend
.venv/bin/uvicorn app.main:app --reload
# → http://localhost:8000

# Frontend
cd frontend
npm run dev
# → http://localhost:3000 (or 3001 if 3000 is taken)
```

Open whichever port Next picked in the browser.

## Verify it works

```bash
# From backend/
.venv/bin/pytest
# → 52 passed in ~3 seconds
```

Then in the UI, try:

- `what do you know about Sarah?` — tests memory recall
- `/write-prd <feature idea>` — kicks off the PRD workflow (routes to Gemma 4)
- `/stakeholder-update weekly rollup` — drafting workflow
- `/meeting-prep Thursday planning` — agenda builder

## Project layout

```
pmomentum/
├── backend/           # FastAPI app
│   ├── app/
│   │   ├── api/       # HTTP + WebSocket endpoints
│   │   ├── core/      # Session engine, tools, memory, skills, LLM clients
│   │   ├── models/    # SQLAlchemy tables
│   │   └── skills/    # SKILL.md files (one dir per skill)
│   ├── alembic/       # DB migrations
│   ├── scripts/       # Manual smoke tests and seed
│   └── tests/         # pytest suite
└── frontend/          # Next.js app
    ├── app/           # App-router pages
    ├── components/    # React components
    └── lib/           # API client, WS client, Zustand store, types
```

## Design docs

The full product spec, architecture, and MVP implementation plan live outside
this repo in the parent workspace. If you're cloning this to contribute, ask
the owner for those docs — they're the why behind the code.

## Development notes

- **Backend auto-reloads** on code edits via `uvicorn --reload`. `.env`
  changes require a manual restart.
- **Frontend hot-reloads** via Next.
- **Adding a new skill:** create `backend/app/skills/<name>/SKILL.md` with
  YAML frontmatter. No code change needed — the loader picks it up on restart.
- **Adding a new tool:** register in `backend/app/core/tools/` and add
  a handler. The session engine discovers tools automatically.
- **Adding a new LLM provider:** create a client module alongside
  `google_client.py` / `groq_client.py`, update the dispatcher in
  `app/core/llm.py`, add pricing in `app/core/cost_tracker.py`.

## License

Private project, no license. All rights reserved.
