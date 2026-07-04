# Momentum

[![CI](https://github.com/adam-rapoport/momentum/actions/workflows/test.yml/badge.svg)](https://github.com/adam-rapoport/momentum/actions/workflows/test.yml)

An AI agent for product management work, packaged as a **macOS desktop app**.
It drafts PRDs, stakeholder updates, meeting prep, release notes and more
through guided skill workflows (slash commands), with persistent memory across
sessions and web search — using whichever LLM provider you have a key for.
Google Docs / Gmail / Calendar integration is coming in a future version.

Built as an MVP with Claude Code as the pair programmer. Still in active
development.

## The desktop app (the main way to run it)

**[Download the latest release](https://github.com/adam-rapoport/momentum/releases/latest)**
— signed + notarized `.dmg` installers for both Apple Silicon and Intel Macs,
with built-in auto-update. See **[INSTALL.md](INSTALL.md)** for the 3-step
install.

Or build it yourself:

```bash
./build-desktop.sh
```

builds a self-contained `.dmg` — a Tauri 2 shell bundling the Next.js UI and
the Python backend frozen into a sidecar binary. No Python, Node, or database
service needed on the machine that runs it. (Source builds target the arch of
the Mac they run on — no cross-compiling — and are unsigned.)

On first launch the app walks you through an onboarding wizard, stores your
API keys encrypted on your Mac, and keeps all data in
`~/Library/Application Support/Momentum/`.

## Stack

- **Backend:** FastAPI (Python 3.12) + SQLAlchemy on **SQLite** — fully
  self-contained, no Postgres or Redis to install. The schema migrates itself
  (Alembic) and seeds a default workspace on startup. The local API is
  protected by a per-launch shared token plus Host/Origin checks, so other
  processes and websites on the machine can't drive the agent.
- **Frontend:** Next.js 15 (static export) + TypeScript + Tailwind + Zustand,
  rendered in the Tauri webview (or a browser during development).
- **LLM providers:** Groq, Google AI Studio (Gemini/Gemma), OpenAI, Anthropic,
  OpenRouter, Mistral, and local models via Ollama. Keys are **optional at
  startup** — enter any subset in the onboarding wizard or Settings; they're
  stored in a Fernet-encrypted vault. Routing is per-turn: a fast model for
  casual/tool-heavy turns, a heavier model for drafting.
- **Web search:** Tavily or Perplexity.
- **Integrations:** Google Docs / Gmail / Calendar is **coming in a future
  version** — the backend is built (see
  [docs/google-connect-setup.md](docs/google-connect-setup.md)) but the app
  currently surfaces it as "coming soon."
- **Desktop shell:** Tauri 2 (Rust) spawning the backend as a PyInstaller
  one-file sidecar on `localhost:8000`.

## Developing (web mode)

Prerequisites: macOS or Linux, Python 3.12+, Node.js 18+. No database service
— SQLite is created automatically.

```bash
git clone https://github.com/adam-rapoport/momentum.git
cd momentum

# Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # optional — the app boots with no .env at all

# Frontend
cd ../frontend
npm ci
```

Then run both, in two terminals:

```bash
# Backend — migrations + seeding run automatically on startup
cd backend
.venv/bin/uvicorn app.main:app --reload
# → http://localhost:8000

# Frontend
cd frontend
npm run dev
# → http://localhost:3000 (or 3001 if 3000 is taken)
```

Open the frontend URL in a browser. With no `.env`, the app starts on the
onboarding wizard — paste an API key for at least one provider there.

## Verify it works

```bash
# From backend/
GROQ_API_KEY=x GOOGLE_AI_API_KEY=x OPENAI_API_KEY=x .venv/bin/pytest -q
# → 442 passed in a few seconds
.venv/bin/ruff check .

# From frontend/
npm run lint && npm run typecheck && npm run build
```

(The placeholder keys only satisfy config at import time — no test calls a
real provider.) CI runs the same checks on every PR: the backend suite against
SQLite, SQLite-with-`DATA_DIR` (desktop-mode config), and Postgres, plus the
frontend lint/typecheck/build, plus an advisory macOS job that freezes the
sidecar and runs its `--selfcheck`.

Then in the UI, try:

- `what do you know about Sarah?` — tests memory recall
- `/write-prd <feature idea>` — kicks off the PRD workflow (routes to the heavy model)
- `/stakeholder-update weekly rollup` — drafting workflow
- `/meeting-prep Thursday planning` — agenda builder

## Project layout

```
momentum/
├── build-desktop.sh        # one-command macOS desktop build (see INSTALL.md)
├── backend/                # FastAPI app
│   ├── app/
│   │   ├── api/            # HTTP + WebSocket endpoints
│   │   ├── core/           # Session engine, tools, memory, skills, LLM clients
│   │   ├── models/         # SQLAlchemy tables
│   │   ├── prompts/        # Static system-prompt sections
│   │   ├── skills/         # SKILL.md workflows (one dir per skill)
│   │   ├── desktop.py      # Desktop entrypoint + frozen-build --selfcheck
│   │   └── security.py     # Local-API token/Origin/Host enforcement
│   ├── alembic/            # DB migrations (applied automatically on startup)
│   ├── momentum.spec      # PyInstaller spec for the sidecar binary
│   ├── requirements-desktop.lock  # pinned deps for reproducible desktop builds
│   ├── scripts/            # Manual smoke tests, seed, lockfile regen
│   └── tests/              # pytest suite (442 tests)
├── frontend/               # Next.js app (static export for the desktop shell)
│   ├── app/                # App-router pages (chat, onboarding, settings)
│   ├── components/         # React components
│   ├── lib/                # API client, WS client, Zustand store, types
│   └── src-tauri/          # Tauri 2 desktop shell (Rust)
└── docs/                   # Setup guides
```

## Development notes

- **Backend auto-reloads** on code edits via `uvicorn --reload`. `.env`
  changes require a manual restart.
- **Frontend hot-reloads** via Next.
- **Adding a new skill:** create `backend/app/skills/<name>/SKILL.md` with
  YAML frontmatter. No code change needed — the loader picks it up on restart.
- **Adding a new tool:** register in `backend/app/core/tools/` and add
  a handler. The session engine discovers tools automatically.
- **Adding a new LLM provider:** create a client module alongside
  `groq_client.py` / `google_client.py` / `openai_client.py`, update the
  dispatcher in `app/core/llm.py`, register models + pricing in
  `app/core/model_registry.py` and `app/core/cost_tracker.py`.
- **Changing backend dependencies:** edit `backend/pyproject.toml`, then run
  `backend/scripts/regen-desktop-lock.sh` so desktop builds stay pinned.

## License

Released under the [MIT License](LICENSE) © 2026 Adam Rapoport.
