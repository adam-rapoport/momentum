# Revamp Handoff — What Was Implemented and Why

*Audience: a fresh Claude Code (or human) session running on the owner's Mac.
This brings you up to speed on the June 2026 revamp of pMomentum and tells you
what still needs doing on real macOS hardware. Read this first; read
[`code-review-revamp-plan.md`](code-review-revamp-plan.md) second — it is the
original review (~90 findings with file:line references and finding IDs like
A1/F8/T9 that commit messages and code comments cite).*

---

## 0. The one-paragraph version

The entire codebase was reviewed, ~90 issues were cataloged, and a 6-phase fix
plan was then **fully executed** on branch `claude/pmomentum-code-review-c8myfm`
(33 commits, **not merged to main** — the owner wants to approve that
explicitly). The backend test suite grew from 188 to **371 passing tests**;
ruff, ESLint, tsc, and the Next.js static export are all green. Everything was
verified in a Linux cloud container **except** things that require macOS: the
Tauri/Rust shell compile, the PyInstaller freeze, the Keychain integration, and
one live-API smoke test. Those are your job — see §6.

## 1. Project snapshot

pMomentum is a macOS desktop app for product managers: a Tauri 2 shell wrapping
a Next.js 15 static-export UI and a FastAPI backend frozen into a PyInstaller
sidecar (SQLite in `~/Library/Application Support/pMomentum/`). The agent core
(`backend/app/core/session_engine.py`) runs a streaming tool-call loop against
a per-turn-routed LLM (Groq / Google AI / OpenAI), with PM "skills"
(SKILL.md workflows), ~23 tools, a pause-for-approval system for side effects
(send email, create calendar event) and deliverables, persistent memory, and
cost tracking.

## 2. How the work is organized

| Unit | Commits | Theme |
|---|---|---|
| Review + plan | `777e459` | The findings catalog and the phase plan |
| Phase 0 | `66666ed` | Security & data-safety hotfixes (contracts everything else builds on) |
| Track A | `57f4483`..`424a54c` | Test harness (no app-code changes) |
| Track B | `8b23b37`..`08a5f64` | Frontend & desktop-shell reliability/UX |
| Track C | `7a48f05` | Packaging, CI, docs |
| Phase 1 | `ae443a1`..`a6c5285` | Core-loop reliability (the critical path) |
| Phase 3 | `33ebc4a`..`696af40` | Architecture cleanup / deduplication |

Standing rule from the owner: **"don't be additive for the sake of it — write
the best code; delete what becomes redundant."** Compatibility shims were
deliberately removed (e.g. `groq_client` no longer re-exports the stream
types); follow the same rule.

**Inspecting the changes:** all commits are pushed to `origin`, so from any
clone:

```bash
git fetch origin main claude/pmomentum-code-review-c8myfm
git diff main...claude/pmomentum-code-review-c8myfm --stat   # the whole revamp
git show ae443a1                                             # any single commit + its message/rationale
git log --oneline main..claude/pmomentum-code-review-c8myfm  # the 30+ commit list
```

Commit messages carry the per-change rationale and cite the finding IDs from
the review doc — prefer `git show` over re-reading whole files when you need
the "what exactly changed here".

## 3. What was implemented, with rationale

### Phase 0 — Security & data-safety (`66666ed`)

* **Local-API trust boundary** (`backend/app/security.py`, wired in `main.py`
  and `api/websocket.py`). *Why:* the backend listened on localhost with no
  auth and no WS origin check — any website in any browser on the machine
  could open `ws://127.0.0.1:8000/ws` and drive the agent (send Gmail, read
  memory); CORS does not protect WebSockets or state-changing requests, and
  DNS rebinding defeats origin reasoning for GETs. *What:* three layers —
  Host allowlist, Origin allowlist, and a **per-launch shared token**: the
  Tauri shell generates it (`src-tauri/src/lib.rs`), passes it to the sidecar
  as `PMOMENTUM_AUTH_TOKEN`, exposes it to the webview via the
  `get_backend_token` IPC command; HTTP sends `X-PMomentum-Token`, WS sends
  `?token=`. `/health` and the Google OAuth callback are token-exempt (the
  callback arrives from the user's real browser; it has its own state token).
  Token unset (web dev, pytest) ⇒ token check skipped, Host/Origin still on.
* **SQLite WAL + `busy_timeout=5000` + `synchronous=NORMAL`**
  (`dependencies.py`). *Why:* concurrent REST + WebSocket writes threw
  intermittent "database is locked".
* **`messages.seq`** (migration `007`, backfilled from rowid). *Why:*
  intra-turn ordering relied on `created_at` with SQLite's 1-second
  resolution; a tool result sorting before its tool_use makes the rebuilt
  provider history invalid and **permanently bricks the session**. All
  history queries now order by `(turn_id, seq)`.
* **Approval idempotency** (`pending_actions.py`, `session_engine.py`): an
  `executing` stamp is committed *before* a staged email/invite is executed,
  the result committed right after, and re-approving an action stuck in
  `executing` refuses to blind-resend (tells the user to verify). *Why:* a
  crash between execute and commit could double-send email.
* Smaller: lazy seed self-heal in `default_user.py` (a one-time seeding
  failure used to mean permanent 500s), Groq `usage or 0` guard
  (`Decimal(None)` killed otherwise-successful turns), CORS
  `allow_credentials=False`.

### Track A — Test harness (tests only)

*Why first:* the 878-line `process_message` loop had **zero** automated tests;
every Phase 1 change needed a safety net that doubles as a spec.

* `tests/integration/test_session_engine.py` — drives the real engine against
  SQLite fixtures with `stream_message` replaced by scripted
  StreamChunk/StreamResult sequences (`_scripted_stream` helper). Covers plain
  turns, tool loops, both pause flows with approve/revise/restart, cancel,
  commit failure, MAX_TOOL_ITERATIONS.
* `test_ws_contract.py` — **pins the exact WS JSON shapes the frontend
  depends on.** Treat these as a contract: fields/codes may be added, never
  removed or renamed.
* `test_rest_api.py`, `test_credentials_vault.py`, `test_vault.py`,
  `test_config_settings.py` (DATA_DIR precedence, vault-key minting),
  `test_execute_tool.py`, `test_memory_store.py`.
* Six `scripts/try_*.py` manual smoke scripts were ported to pytest and
  **deleted**. The surviving `try_*` scripts genuinely need live keys/OAuth.

### Track B — Frontend & desktop shell

* **Streaming state machine** (`lib/ws.ts`, `lib/store.ts`, `lib/api.ts`).
  *Why:* the #1 "clunky" cause — a WS drop mid-turn stranded the UI on
  "thinking…" forever; the `stream.done`→refetch pipeline raced fast
  follow-ups; no fetch had a timeout. *What:* `onclose` finalizes all
  in-flight sessions and resyncs on reconnect; per-session refetch sequence
  numbers kill out-of-order overwrites; `AbortSignal.timeout` on every
  request; reconnect-timer/handler cleanup in `disconnect()`; cost preserved
  on error paths; optimistic user messages get unique IDs, a failed-send
  marker, and a Retry button.
* **Desktop-dead links** (`components/ExternalLink.tsx`). *Why:* every "Open
  in Google Docs" anchor silently did nothing inside the Tauri webview — the
  flagship deliverable flow's payoff was broken. *What:* one component
  calling `openExternal()` (Tauri opener plugin), used directly and as the
  ReactMarkdown `a` renderer.
* **Boot/onboarding robustness**: `completeOnboarding()` failures now surface
  with retry instead of looping /chat↔/onboarding forever; the wizard treats
  already-configured providers as advanceable (re-running it no longer
  demands re-pasted keys); multi-file upload stale-closure fixed; BootGate
  never hard-fails (polls forever with "still starting…" copy); the Rust
  shell handles `CommandEvent::Terminated` — logs, emits
  `backend-terminated`/`backend-respawned` events, and attempts **one**
  respawn.
* **Dynamic port + graceful shutdown** (`src-tauri/src/lib.rs`,
  `lib/desktop.ts`). *Why:* port 8000 was hardcoded into the static export;
  a squatter (e.g. a dev uvicorn) made the packaged app silently talk to the
  wrong process or hang on boot; shutdown was SIGKILL-only. *What:* the shell
  probes 8000, falls back to a free OS-assigned port, passes it via
  `PMOMENTUM_PORT` (+ `GOOGLE_REDIRECT_URI` when off-default) and the
  `get_backend_port` IPC command; `api.ts`/`ws.ts` derive base URLs at
  runtime. Shutdown: SIGTERM to the subtree, 1.5 s grace, SIGKILL sweep.
* **CSP** (`tauri.conf.json`): real policy replacing `csp: null` — remote
  scripts/objects/frames blocked, connections limited to localhost + Tauri
  IPC. `script-src` keeps `'unsafe-inline'` because Next's static export
  hydrates via inline scripts.
* **UX debt**: near-bottom-only autoscroll + "Jump to latest"; session-load
  loading/error states with retry; header cost seeded from the session
  record; sidebar rename (inline) + two-step delete; copy button on
  assistant bubbles; "stopped by you" indicator.

### Track C — Packaging, CI, docs

* **Arch-honest build** (`build-desktop.sh`). *Why:* `TARGET_TRIPLE` was
  hardcoded `x86_64-apple-darwin` while PyInstaller freezes for the *host*
  arch — built on Apple Silicon it produced an arm64 binary labeled x86_64.
  *What:* triple derived from `rustc -vV`, passed to `tauri build --target`.
  Native AS build = run the whole script on AS hardware (PyInstaller cannot
  cross-compile). Bundle paths now include the triple.
* **Reproducible builds**: `backend/requirements-desktop.lock` (regenerate
  with `backend/scripts/regen-desktop-lock.sh`) consumed by the build script;
  `pmomentum.spec` collects only the Google subpackages actually imported +
  `copy_metadata` for the SDKs.
* **Extended `--selfcheck`** (`app/desktop.py`): now also runs alembic against
  a temp SQLite DB and imports the google-genai/openai/google-api-client
  SDKs — catches PyInstaller omissions before shipping.
* **CI** (`.github/workflows/test.yml`): frontend job (ESLint flat config +
  tsc + next build), ruff for the backend, a `DATA_DIR` desktop-mode matrix
  leg, Postgres service only on the Postgres leg, push trigger restricted to
  main, and an **advisory macOS job** that freezes the sidecar and runs the
  frozen selfcheck (`continue-on-error: true` until proven).
* **README/INSTALL rewritten** for the actual stack (SQLite, three providers,
  optional keys, desktop-first). Versions aligned at 0.1.0;
  `tauri.conf.json` is the version source of truth.

### Phase 1 — Core-loop reliability

* **Real cancellation** (items 6–7, `api/websocket.py` + `session_engine.py`).
  *Why:* the WS read loop `await`ed the whole turn inline, so a
  `session.cancel` frame sat unread until the turn finished — Stop could
  never work; the engine also only checked the flag on text chunks. *What:*
  turns run as `asyncio.Task`s (process-wide registry keyed by session_id);
  the read loop stays free; cancel is checked at the top of each loop
  iteration, before each tool, and after each batch; the provider stream is
  closed and its usage recorded; partial text is persisted with an
  "interrupted" marker; the loop body is `try/finally`-wrapped so contextvar
  and cancel-key cleanup always run. A second `session.message` for a busy
  session gets `TURN_IN_PROGRESS` (plus a per-session `asyncio.Lock` as
  belt-and-braces). Client disconnect cancels that connection's tasks;
  committed work survives and the frontend resyncs.
* **Pending-action queue** (item 8). *Why:* a single
  `session_metadata['pending_action']` slot meant two staged actions in one
  batch silently overwrote each other. *What:* a list under
  `pending_actions` (legacy singular key still read), one approval pause per
  action, FIFO; `_rewrite_staged_tool_result` matches the specific action via
  a recorded `call_id`. While paused, free-text that isn't
  approve/revise/restart gets `APPROVAL_REQUIRED` instead of running a model
  turn that could re-fire side effects; the classifier accepts natural
  phrasing ("yes, send it", "don't") with deliberately small word lists.
* **Error taxonomy + retry** (item 9): SDK errors from all three providers
  map to `MODEL_AUTH_ERROR` / `MODEL_RATE_LIMITED` / `MODEL_CONTEXT_TOO_LONG`
  / `MODEL_TOOL_CALL_FAILED` / `MODEL_API_ERROR`; transient failures retry
  (2 attempts, backoff) **only if no chunk was yielded yet** — a partial
  stream is never silently replayed. MAX_TOOL_ITERATIONS exhaustion now makes
  one final no-tools "wrap up" call instead of ending in silence.
* **Per-tool timeouts** (item 11, `tools/__init__.py`): category budgets
  (research/integrations 60 s, documents 30 s, default 15 s) via
  `asyncio.wait_for`, per-tool `timeout_seconds` override; a hung Google call
  no longer wedges the turn.
* **Context-window management** (item 10). *Why:* the engine sent the entire
  history + ~8k-token prompt every turn; long sessions slowed, then
  hard-failed. *What:* every persisted message stores `token_count_estimate`
  (~4 chars/token); `ModelEntry.context_window` on every registry entry; the
  engine budgets (context − prompt − user message − 2k response reserve) and
  drops **whole turns** oldest-first (never splitting tool_use/tool_result
  pairs), inserting a system note marking the cut. Newest turn always
  survives. Summarize-then-compact (`is_compacted`) is deliberately deferred;
  the history query already filters on it.

### Phase 3 — Architecture cleanup

* **Unified LLM client** (item 18): `app/core/llm_types.py`
  (StreamChunk/StreamResult/ToolCall) + `app/core/openai_compat.py` — the
  single delta-accumulation streaming loop that was previously triplicated
  (and already diverging). `groq_client`/`openai_client`/`google_client` are
  thin config shims; google keeps its thought-stripper as a wrapper. **No
  re-export shims** — import the types from `llm_types`.
  `model_registry.infer_provider()` is the single source of provider truth;
  `model_router` falls back to any *available configured* model instead of
  hardcoded Groq (fixing "any LLM as brain" for non-Groq users), and raises
  → WS `NO_PROVIDER_CONFIGURED` when nothing is configured.
  `HEAVY_SLASH_COMMANDS` derives from `load_skills()`.
* **Gemini 3.x native-SDK path fixed** (item 19) — all three suspected bugs
  verified against the vendored google-genai 2.8.0 source: schemas via
  `parameters_json_schema`, consecutive tool results grouped into one
  `Content` (parallel-call requirement), thought signatures persisted inside
  the `tool_use` content block (survive restarts; old process-local cache
  deleted) and stripped before any OpenAI-format wire. **Never run against
  the live API** — see §6.
* **Registry/pricing** (item 20): test pins every registry model to a price
  entry; unknown models log once instead of silent $0;
  `sessions.llm_provider/llm_model` updated per turn so the UI shows the
  real brain.
* **Data hygiene** (item 21, migration `008`): `ON DELETE CASCADE` across the
  FK chain (SQLite `batch_alter_table`; tested on fresh **and** upgraded
  DBs); dead plaintext-shaped `organizations.llm_api_keys` column dropped;
  `UTCDateTime` TypeDecorator makes all timestamps read back tz-aware UTC
  (REST timestamps now carry an offset). The full org/user collapse was
  explicitly left out of scope.
* **Engine polish** (item 22): never-advancing `active_skill_phase` dropped
  (the prompt no longer claims a bogus "current phase"); glibc-only
  `%-d`/`%-I` strftime replaced (Windows-safe); prompt reflects the real
  search provider/platform instead of hardcoded claims; stale "wiring lands
  in Chunk C" AwaitReview output replaced; empty//deep-only messages
  rejected (`VALIDATION_ERROR`); outbound WS frames serialized through the
  pydantic schemas in `schemas/websocket.py` (updated to reality first) so
  backend/frontend can't drift; the WS read loop survives malformed frames.
* **Vault key → macOS Keychain** (item 23, `config.py`): resolution order is
  Keychain (service `pMomentum`, account `vault-key`) > existing `vault.key`
  file (auto-migrated into the Keychain, file kept for rollback) > fresh mint.
  Degrades silently when `keyring` is unavailable (Linux CI, tests). *Why:*
  the Fernet key sat in plaintext next to the DB it encrypts.
* **Memory hygiene** (item 24): slug collisions suffix `-2/-3/…` instead of
  silently overwriting; the markdown file is written only after a successful
  DB flush.

## 4. Contracts a fresh session must not break

1. **WS event shapes and error codes** — pinned in
   `backend/tests/integration/test_ws_contract.py`. Additive changes only.
   Current error codes the frontend maps to banner titles
   (`frontend/components/ChatView.tsx`): `MODEL_TOOL_CALL_FAILED`,
   `MODEL_AUTH_ERROR`, `MODEL_RATE_LIMITED`, `MODEL_CONTEXT_TOO_LONG`,
   `MODEL_API_ERROR`, `TURN_IN_PROGRESS`, `APPROVAL_REQUIRED`, `TOOL_ERROR`,
   `DB_ERROR`, `WS_DISCONNECTED`, `WS_UNAVAILABLE`, `NO_PROVIDER_CONFIGURED`,
   `VALIDATION_ERROR`, `UNKNOWN_MESSAGE_TYPE`, `NOT_FOUND`.
2. **Shell ⇄ sidecar ⇄ webview contract**: `PMOMENTUM_AUTH_TOKEN` +
   `PMOMENTUM_PORT` (+ `GOOGLE_REDIRECT_URI` off-default) env vars into the
   sidecar; `get_backend_token` / `get_backend_port` IPC commands;
   `X-PMomentum-Token` header / `?token=` WS param.
3. **Message ordering**: always `(turn_id, seq)`, never `created_at`. Every
   new `Message` row must set `seq` (engine helper `_take_seq`) and
   `token_count_estimate`.
4. **Tool error protocol**: tool outputs starting with `"Error"` mark
   `is_error=True` (string protocol kept deliberately; structured results
   were considered and deferred).
5. **Pending actions**: list under `session_metadata["pending_actions"]`
   (legacy singular `pending_action` still read first); two-phase
   execute-with-`executing`-stamp for idempotency.

## 5. Verification status (what's already proven)

On the branch head: 371 backend tests pass (`pytest`), `ruff check` clean,
`eslint --max-warnings 0` clean, `tsc --noEmit` clean, `next build` static
export clean, unfrozen `python -m app.desktop --selfcheck` passes all 8
checks, migrations 001→008 apply on fresh and upgraded SQLite DBs, and the
token/origin/host enforcement was smoke-tested live over HTTP and WS.

Run them yourself:

```bash
# Backend (from backend/; venv with: python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]")
GROQ_API_KEY=x GOOGLE_AI_API_KEY=x OPENAI_API_KEY=x .venv/bin/pytest -q   # placeholder keys matter
.venv/bin/ruff check .
# Frontend (from frontend/; npm ci)
npm run lint && npm run typecheck && npm run build
```

## 6. YOUR TODO — things only a real Mac can verify

In priority order:

1. **Compile the Rust shell.** `cd frontend/src-tauri && cargo check` (or just
   step 3). The cloud container had no macOS/GTK toolchain, so the shell
   changes (token generation, port probing, `get_backend_token`/
   `get_backend_port` commands, `spawn_backend` respawn path, SIGTERM
   shutdown) are API-checked against vendored crate sources but **never
   compiled**. Expect at worst small fix-ups (borrow/typing), not design
   issues.
2. **Regenerate the desktop lockfile on macOS**:
   `cd backend && ./scripts/regen-desktop-lock.sh` — the `keyring` pins were
   appended by hand with platform markers and should be replaced by a real
   macOS resolution.
3. **Full build**: `./build-desktop.sh`. Confirm it reports the correct
   target triple for your machine, the frozen `--selfcheck` passes (now 8
   checks), and the `.dmg` lands under
   `frontend/src-tauri/target/<triple>/release/bundle/dmg/`.
4. **First-launch checks on the installed app**: window appears; BootGate
   resolves; **if you had an existing install**, confirm `vault.key` was
   migrated into the Keychain (Keychain Access → search "pMomentum") and
   stored API keys still decrypt; with a dev uvicorn squatting on 8000,
   confirm the app picks another port and still works; ⌘Q leaves nothing
   bound on the port (`lsof -i :8000`).
5. **Live smoke tests** (need real keys): one casual turn per provider
   (Groq/OpenAI), and **one multi-turn, tool-using skill flow on a Gemini
   3.x model** — that native-SDK path is wire-correct per the SDK source but
   has never spoken to the live API (thought-signature replay is the thing
   to watch). Also: Stop button mid-generation (text should keep the
   "interrupted" marker), an email approval flow, and an "Open in Google
   Docs" click.
6. **CI sanity**: the advisory `desktop-sidecar-macos` job is
   `continue-on-error`; once it's green a few times, consider making it
   blocking.

## 7. Known deferred work (deliberate, not forgotten)

- **History compaction** (summarize-then-mark `is_compacted`) — the sliding
  window ships; compaction is the follow-up. Schema is ready.
- **Memory auto-extraction after conversations** (review finding A32) —
  feature work, was out of cleanup scope.
- **Full org/user data-model collapse** (P8) — only hygiene was done; the
  multi-tenant tables remain behind `default_user.py`.
- **Code signing + notarization** (and the PyInstaller onedir switch it
  requires) — the build is still unsigned/internal; the build-script header
  documents the path.
- **`tauri-plugin-single-instance`** — skipped; the dynamic-port fallback
  already prevents the second-instance corruption scenario.
- **Migration 003 `llm_model` server_default mismatch** (P13) — cosmetic,
  needs a SQLite table rebuild; documented in the Phase 3 report instead.
- **Structured tool results** (replacing the `"Error"` string protocol) —
  considered in Phase 1, deferred to keep the diff contained.

## 8. Branch state

Everything lives on `claude/pmomentum-code-review-c8myfm`, pushed to origin.
**Nothing is merged to main** — the owner explicitly reserved that decision.
If asked to merge or open a PR, get their approval first.
