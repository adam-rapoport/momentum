# Momentum — Full Code Review & Revamp Plan

*Review date: 2026-06-09. Reviewed at commit `741dd48`. No code was changed as part of this review.*

---

## 1. What the app is (as built)

Momentum is a **macOS desktop app** (Tauri 2 shell, Intel build, Rosetta on Apple Silicon)
wrapping:

- **Frontend:** Next.js 15 static export (React, Tailwind, Zustand) rendered in the Tauri
  webview. Chat UI with streaming, tool-call cards, an approval bar for risky actions,
  onboarding wizard, settings, memory and documents panels.
- **Backend:** FastAPI (Python 3.12) frozen into a one-file PyInstaller sidecar, spawned by
  the Tauri shell, listening on `localhost:8000` (HTTP + WebSocket). SQLite at
  `~/Library/Application Support/Momentum/`, in-process KV store (Redis was removed),
  Fernet-encrypted credential vault.
- **Agent core:** a session engine (`backend/app/core/session_engine.py`, ~880 lines) that
  runs a streaming tool-call loop against a per-turn-routed LLM (Groq / Google AI / OpenAI),
  with 10 PM "skills" (SKILL.md workflows triggered by slash commands), 23 tools (memory,
  documents, web search/fetch, Gmail, Calendar, Google Docs), a pause-for-approval system
  for side-effecting actions (send email, create event) and deliverables (AwaitReview),
  persistent memory (markdown files + DB records), and per-turn cost tracking.

The intent — "an AI agent tool for PMs that can use any available LLM as its brain" — is
mostly implemented, but the review found that **several core promises are broken in
practice**: cancel doesn't work, "any LLM as brain" fails for non-Groq-only users, the
approval system can drop or double-fire side effects, long sessions hard-fail, the local
API is open to any website on the machine, and the desktop UI has multiple "stuck forever"
states. These, more than any single feature gap, are why testing feels clunky.

## 2. Verdict at a glance

| Area | State |
|---|---|
| Agent loop (streaming, tools, skills) | Works on the happy path; **structurally broken** cancel, approval-slot, and history-ordering issues |
| Multi-LLM routing | Groq-centric; Google/OpenAI-only setups break; Gemini 3.x path is never-executed code |
| Local API security | **Wide open** — no WS origin check, no HTTP auth; any website can drive the agent |
| Persistence (SQLite) | Migrations are clean, but no WAL/busy-timeout → intermittent "database is locked" |
| Frontend state | Several races/leaks that strand the UI in "thinking…" forever |
| Desktop shell | No sidecar crash detection, SIGKILL-only shutdown, hardcoded port 8000, `csp: null` |
| Packaging | Build script lies about architecture on Apple Silicon; no dependency lockfile |
| Tests/CI | ~170 tests but **zero coverage of the core loop, WS contract, REST API, vault**; no frontend CI |
| Docs | README describes the removed Postgres+Redis stack |

---

## 3. Critical findings (fix-first list)

These ten issues explain most observed flakiness and all of the serious risk.

### C1. "Stop generation" cannot work — WS read loop blocks during a turn
`backend/app/api/websocket.py:49-77` awaits `_handle_user_message(...)` inline inside the
same loop that does `ws.receive_json()`. A `session.cancel` sent mid-turn sits unread in
the socket buffer until the turn finishes. Compounding it, the engine only checks the
cancel flag on **text** chunks (`session_engine.py:615-619`), never between tool
iterations or before tool execution.
**Fix:** run `process_message` consumption as an `asyncio.Task` keyed by session so the
read loop stays free; on cancel, set the KV flag *and* cancel the task; check the flag at
the top of each loop iteration and before each tool call.

### C2. Local backend is open to any website (no WS origin check, no HTTP auth)
`websocket.py:50` accepts unconditionally; WebSockets are not subject to CORS, so any web
page in any browser on the machine can connect to `ws://127.0.0.1:8000/ws`, drive the
agent, send email through the user's Gmail, and read responses. The HTTP API likewise has
no auth and no Host/Origin validation (`app/main.py:104-113` CORS only stops cross-origin
*reads*, not state-changing requests; DNS rebinding bypasses it entirely).
**Fix:** (a) reject WS connections whose `Origin` isn't the app (`tauri://` /
`http://localhost:<app-port>`); (b) generate a per-launch secret in the Tauri shell, pass
it to the sidecar via env and to the webview via Tauri IPC, require it as a header on every
HTTP request and as a query param/first message on the WS; (c) add Host-header validation
middleware.

### C3. UI strands in "thinking…" forever on WS drop or wedged refetch
`frontend/lib/ws.ts:41-48` + `lib/store.ts:121-126` — if the socket drops mid-turn,
`isStreamingBySession` stays `true` with no recovery; nothing on reconnect resyncs.
`lib/api.ts` has **no request timeouts**, so the `getSession` refetch that finalizes a turn
can also hang forever. This is the single biggest "clunky" driver.
**Fix:** on `onclose`, finalize all in-flight sessions; on reconnect, refetch and resync;
add `AbortSignal.timeout(...)` to all fetches; add a turn-generation counter so a stale
`finalizeStream` can't clobber the next turn (race at `ws.ts:189-208`).

### C4. Approval system can drop or double-fire side effects
- Single `pending_action` slot (`core/pending_actions.py:56-64`): two staged actions in one
  batch (parallel `SendEmail` calls, or the Gemini concatenated-JSON salvage path at
  `session_engine.py:713-729`) silently overwrite each other; stale "[Pending approval]"
  tool results survive because `_rewrite_staged_tool_result` rewrites only the first match.
- Approve executes the email **before** the commit (`session_engine.py:300-336`); a crash
  between execute and commit leaves the session still `awaiting_review` → approving again
  double-sends.
- Free-text replies while paused (anything other than exact "approve"/"revise"… —
  `_classify_review_response` at `session_engine.py:201-223`) run a full model turn with
  the pause still in place, letting the model restage actions.
**Fix:** make `pending_action` a list (or reject a second stage while one is pending);
execute-after-commit with an "executing" state marker for idempotency; block side-effecting
tools while a session is paused; loosen response classification.

### C5. No context-window management at all
`session_engine.py:557-571` loads the **entire** history plus an ~8k-token system prompt
every turn. `is_compacted` and `token_count_estimate` exist in the schema but nothing ever
sets them. Long sessions get slower, costlier, then hard-fail with an opaque provider
error.
**Fix:** implement compaction (summarize-then-mark-compacted) or at minimum a token-budgeted
sliding window, plus a friendly "conversation is long" UX path.

### C6. "Any LLM as brain" breaks for non-Groq users
`core/model_router.py:70,81` hardcodes fallback to `settings.groq_model`; a user with only
an OpenAI or Google key gets "GROQ_API_KEY is not configured" turn failures. Provider
derivation is duplicated and inconsistent (`credentials.py:60-70` prefix heuristics vs the
registry vs `llm.py:64` fallback). The Gemini 3.x registry entries route to
`google_genai_client.py`, which its own docstring admits is never-executed code, with at
least three likely API-contract bugs (raw JSON-Schema `additionalProperties` passed to
`types.Schema`; tool results not grouped to match parallel function calls; process-local
`thought_signature` cache lost on every sidecar restart). Several registry model IDs and
the pricing table have drifted from each other (`model_registry.py:90-118` vs
`cost_tracker.py:33`).
**Fix:** fall back to any *available* configured model; make the registry the single source
of provider truth; integration-test the genai path before exposing Gemini 3.x; persist
thought signatures in the tool_use block; validate model IDs against live `/models` at
settings time.

### C7. Message ordering can permanently corrupt a session
`models/message.py:22-24` orders turn messages by `created_at` with SQLite's 1-second
`CURRENT_TIMESTAMP` resolution — every message in a tool batch ties, and ordering between
an assistant tool_use message and its tool results is rowid-luck. One wrong sort →
invalid provider history → **every subsequent turn 400s**, bricking the session.
**Fix:** add a monotonic `seq` column per session and order by it.

### C8. SQLite runs without WAL or busy_timeout
`app/dependencies.py:15-21` only sets `foreign_keys=ON`. REST writes overlapping a WS turn
commit intermittently throw "database is locked".
**Fix:** add `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`,
`PRAGMA synchronous=NORMAL` in the same connect listener.

### C9. Build script produces mislabeled binaries on Apple Silicon
`build-desktop.sh:25,41,46` hardcodes `TARGET_TRIPLE="x86_64-apple-darwin"` while
PyInstaller builds for the **host** arch and `tauri build` gets no `--target`. Built on an
M-series Mac, the output is an arm64 sidecar named `-x86_64-apple-darwin` — a lying
artifact. There is also no Python lockfile (`pyproject.toml` is floor-only `>=`), so every
desktop build freezes whatever pip resolves that day.
**Fix:** derive the triple from `rustc -vV`; pass `--target` to tauri; add a lockfile
(uv/pip-compile) used by the build. This is also the on-ramp for native Apple Silicon.

### C10. The core loop has zero automated tests
`session_engine.process_message` (497-874), the WS event JSON contract, the REST API, the
credential vault round-trip, and desktop-mode config resolution are all untested — guarded
only by 20 manual `scripts/try_*.py` files. The conftest even anticipates porting them
("becomes mechanical") — it never happened. There is **no frontend CI** at all, and
`npm run lint` is non-functional (no ESLint config exists).
**Fix:** see the test plan in Phase 5.

---

## 4. Full findings catalog

### 4.1 Agent core (`backend/app/core`)

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| A1 | crit | Cancel never delivered mid-turn (blocking WS read loop) | `api/websocket.py:49-77` |
| A2 | high | Cancel flag only checked on text chunks; tools uninterruptible | `session_engine.py:615-619` |
| A3 | high | No per-session serialization — concurrent turns corrupt `turn_count`/history | `session_engine.py:576` |
| A4 | high | Single `pending_action` slot drops staged side effects | `pending_actions.py:56-64`, `session_engine.py:387-405,713-729` |
| A5 | high | Approve executes before commit — double-send window | `session_engine.py:300-336,590` |
| A6 | med | Free-text while paused runs a full turn with pause intact; exact-match classifier | `session_engine.py:201-223,521-526,777` |
| A7 | high | `created_at` (1s resolution) ordering can produce invalid provider history | `models/message.py:22-24`, `session_engine.py:557-561` |
| A8 | high | No history truncation/compaction; `is_compacted` never set | `session_engine.py:557-571` |
| A9 | med | No `try/finally` around the loop — contextvar/cancel-key leak, partial text lost on error | `session_engine.py:608-874` |
| A10 | med | Cancelled turns discard usage/cost and abandon the provider stream | `session_engine.py:624` |
| A11 | med | `MAX_TOOL_ITERATIONS` exhaustion is silent to the user | `session_engine.py:854-857` |
| A12 | high | Never-executed google-genai path: schema `additionalProperties`, ungrouped function responses, settable-`thought_signature` assumption | `google_genai_client.py:102,158,163-178` |
| A13 | med | `thought_signature` cache process-local; lost on sidecar restart | `google_genai_client.py:55-66` |
| A14 | low | Groq client: `usage.prompt_tokens` can be `None` → `Decimal(None)` TypeError | `groq_client.py:121-123` |
| A15 | med | Error taxonomy only understands OpenAI SDK; no retries/backoff on 429/5xx | `api/websocket.py:171-203` |
| A16 | high | Model fallback hardcoded to Groq env defaults | `model_router.py:70,81` |
| A17 | med | Provider derived three different ways (registry vs prefix heuristics vs llm.py fallback) | `credentials.py:60-70`, `llm.py:64` |
| A18 | med | Registry/pricing/model-ID drift (`gemma-4-31b-it`, gemini-3.x ids vs `gemini-3-flash-preview` priced but unregistered; `gpt-4o` flagged stale) | `model_registry.py:90-118`, `cost_tracker.py:33` |
| A19 | low | `HEAVY_SLASH_COMMANDS` hardcoded copy of skills registry | `model_router.py:25-36` |
| A20 | low | `Session.llm_provider/llm_model` columns are dead/wrong state | `models/session.py:23-26` |
| A21 | low | Unknown model → silent $0 cost | `cost_tracker.py:61-63` |
| A22 | med | `active_skill_phase` never advances past "intake" — misleads the model every turn | `session_engine.py:436`, `system_prompt.py:170` |
| A23 | med | No per-tool timeout; error protocol is `output.startswith("Error")` | `tools/__init__.py:103-128` |
| A24 | med | `%-d`/`%-I` strftime crashes on Windows, per-turn | `system_prompt.py:68`, `tools/utility.py:25` |
| A25 | low | Prompt hardcodes "Groq + Llama 3.3" and "Tavily (active)" regardless of config | `system_prompt.py:81,137-138` |
| A26 | low | `AwaitReview` tool output still says "wiring lands in Chunk C" — fed to the model | `tools/documents.py:168-192` |
| A27 | low | Multi-word skill trigger keywords activate on casual mentions | `skills/__init__.py:154-159` |
| A28 | low | `save_memory` writes files before commit; slug collisions overwrite silently | `memory/store.py:163-228` |
| A29 | low | `/deep` alone persists an empty user message → assistant turn with no user turn | `session_engine.py:513`, `model_router.py:45-57` |
| A30 | low | Outbound WS pydantic schemas are dead code and drifted from hand-built dicts | `schemas/websocket.py:42-49` |
| A31 | design | `StreamChunk`/`StreamResult` live in `groq_client`; three near-identical streaming clients already diverging | `llm.py`, `groq_client.py`, `openai_client.py`, `google_client.py` |
| A32 | gap | No memory auto-extraction after conversations; only on doc upload | `memory/extract.py` |
| A33 | gap | No `max_tokens`/context-length guards on any request; no tool progress events | engine-wide |

### 4.2 API, persistence, security (`backend/app`)

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| P1 | crit | No origin check on WS — any website can drive the agent | `api/websocket.py:48-50` |
| P2 | high | No HTTP auth / Host validation — CSRF + DNS-rebinding side effects | `main.py:104-113`, all routers |
| P3 | high | Fernet vault key in plaintext next to the DB it encrypts | `config.py:162-179` |
| P4 | high | No WAL/busy_timeout → "database is locked" under concurrent writes | `dependencies.py:9-21` |
| P5 | med | Seeding failure swallowed at boot → permanent 500s on a "healthy" app | `main.py:83-88`, `default_user.py:33-49` |
| P6 | med | Naive UTC timestamps serialized without offset → frontend reads as local time | `models/base.py:24-30` |
| P7 | med | No `ON DELETE` cascades anywhere — future hard-delete orphans rows | all FK models |
| P8 | med | Full multi-tenant schema (orgs/users/roles/plans) retained for a single-user app | `organization.py`, `user.py`, `default_user.py` |
| P9 | med | Port-8000 bind failure crashes the sidecar with an opaque traceback | `desktop.py:110` |
| P10 | low | `organizations.llm_api_keys` plaintext-key-shaped dead column | `organization.py:18` |
| P11 | low | Sessions endpoints don't scope by user (latent IDOR if multi-user returns) | `api/sessions.py:54-99` |
| P12 | low | WS read loop dies silently on non-JSON/non-dict frames | `api/websocket.py:52-54` |
| P13 | low | Migration 003 `llm_model` server_default ≠ model default | `alembic/versions/003_*` |
| P14 | low | `allow_credentials=True` with broad localhost regex | `main.py:109-110` |
| P15 | ok | Migrations are SQLite-safe and match models; OAuth state flow is correct; frozen-path handling is correct | — |

### 4.3 Frontend + Tauri shell (`frontend`)

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| F1 | crit | WS drop mid-turn strands `isStreaming=true` forever — permanent "thinking…" | `lib/ws.ts:41-48`, `lib/store.ts:121-126` |
| F2 | high | `stream.done` async-refetch race clobbers the next turn's chunks | `lib/ws.ts:189-208` |
| F3 | high | No fetch timeouts anywhere — wedged backend = pending promises forever | `lib/api.ts:12-35` |
| F4 | high | All "Open in Google Docs" links are plain anchors — dead in the Tauri webview (flagship flow broken on desktop) | `ToolCallBlock.tsx:101-112`, `ApprovalBar.tsx:130-140`, `DocumentsPanel.tsx:132-141`; also markdown links `MessageBubble.tsx:23` |
| F5 | high | Onboarding ping-pong: `finish()` swallows `completeOnboarding()` failure, BootGate bounces back forever | `OnboardingWizard.tsx:130-138`, `BootGate.tsx:42-45` |
| F6 | high | "Restart wizard" dead-ends users who won't re-paste already-stored keys | `OnboardingWizard.tsx:140-144` |
| F7 | high | `csp: null` — no Content-Security-Policy in the privileged webview | `tauri.conf.json:31` |
| F8 | high | Hardcoded port 8000 baked into the static export; no conflict detection, no single-instance guard; BootGate happily polls a foreign process on 8000 | `next.config.mjs:10-13`, `lib/api.ts:9`, `lib/ws.ts:6`, `src-tauri/src/lib.rs` |
| F9 | high | No sidecar crash detection (`CommandEvent::Terminated` ignored) — 60s blank boot then generic error | `src-tauri/src/lib.rs:48-54` |
| F10 | med | SIGKILL-only shutdown, direct children only — no flush, possible orphans; no parent-watchdog in backend (Tauri force-kill orphans the sidecar on :8000, breaking the next launch) | `src-tauri/src/lib.rs:17-23` |
| F11 | med | `disconnect()` doesn't cancel reconnect timer or detach handlers — zombie reconnects, false "disconnected" header | `lib/ws.ts:55-59` |
| F12 | med | Error paths reset displayed session cost to $0 | `lib/ws.ts:102-109,235` |
| F13 | med | Optimistic user message never rolls back on send failure; `local-${Date.now()}` key collisions | `lib/store.ts:102-119` |
| F14 | med | Approve/Revise optimistic with no recovery — approval bar vanishes on send failure | `ChatView.tsx:173-186` |
| F15 | med | Forced auto-scroll on every chunk — can't scroll up while streaming | `ChatView.tsx:154-158` |
| F16 | med | No loading/error UI for session fetch (blank chat on failure) | `ChatView.tsx:103-152` |
| F17 | med | /settings has no BootGate; SettingsApp swallows errors — providers look "Not connected" against a dead backend | `app/settings/*`, `SettingsApp.tsx:27-36` |
| F18 | med | GtkyStep multi-file upload stale closure — only last file recorded | `GtkyStep.tsx:67-73` |
| F19 | med | Opener capability allows arbitrary model-controlled URLs | `capabilities/default.json:11` |
| F20 | med | Chat hard-coded light theme vs themed settings; both side panels always mounted (~380px chat at default width) | chat components, `app/chat/layout.tsx:16-22` |
| F21 | med | Out-of-order session refetches can overwrite newer messages | `lib/ws.ts:189-208` |
| F22 | low | Global errors (no session_id) swallowed; `finalizeStream` cancelled-param dropped; sidebar reorders on open; slash-menu Enter/Escape quirks; no a11y on menu/approval bar; BootGate 60s hard ceiling; duplicated prefs fetch; dead `ureq` dep; `bundle.android` noise; meta-refresh white flash on `/` | various (see agent notes) |
| F23 | gap | Missing: session rename/delete UI (API exists), retry-send, copy buttons, "stopped" indicator, cost not seeded from session record, code-block highlighting | — |

### 4.4 Tests, CI, packaging, docs

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| T1 | crit | `process_message` (878 lines), `_history_to_llm_messages`, `_rewrite_staged_tool_result` — zero tests | `session_engine.py` |
| T2 | high | WS happy-path JSON contract untested (only error mapping) | `tests/test_error_handling.py` |
| T3 | high | Vault/credentials round-trip untested (`test_credentials.py` punts to a Postgres-era script) | `core/credentials.py:89-167` |
| T4 | high | Desktop-mode config (`DATA_DIR`, vault-key minting, atomic write) untested; no CI leg runs PyInstaller `--selfcheck` | `config.py:123-193` |
| T5 | high | REST endpoints essentially untested | `api/*.py` |
| T6 | high | No frontend CI; `next lint` non-functional (no ESLint config); no tsc/build check | `.github/workflows/test.yml`, `package.json:9` |
| T7 | med | `test_pending_actions.py` mocked-to-death (SimpleNamespace sessions, AsyncMock execution) | `tests/test_pending_actions.py:27-35` |
| T8 | med | ~10 of 20 `try_*.py` scripts are automatable coverage that was deferred | `scripts/` |
| T9 | crit | Hardcoded `x86_64-apple-darwin` + host-arch PyInstaller = mislabeled arm64 builds on Apple Silicon | `build-desktop.sh:25,41,46` |
| T10 | high | Apple Silicon path actively blocked by the script; needs per-arch PyInstaller + `tauri build --target` (or universal) | `build-desktop.sh` |
| T11 | med | No Python lockfile — non-reproducible desktop binaries | `pyproject.toml:6-35` |
| T12 | med | `collect_submodules("google")` over-collection; no `copy_metadata`; `--selfcheck` doesn't exercise alembic-on-temp-DB or Google SDK import | `momentum.spec:30,36-46` |
| T13 | med | One-file PyInstaller mode: slow cold start and the blocker for real signing/notarization | `momentum.spec`, `build-desktop.sh` header |
| T14 | med | CI: Postgres service boots for the SQLite leg; push+PR double-runs; no key-absent registry test | `test.yml` |
| T15 | high | README documents the removed stack (Postgres 16 + Redis required, keys "required", no mention of the desktop app, manual migrate/seed steps, two-provider story) | `README.md` |
| T16 | low | Version quadruplicated across pyproject/package.json/tauri.conf/Cargo.toml; INSTALL.md "for Intel Macs" only true if built on Intel; stale module docstrings | various |

---

## 5. Revamp plan

Phased so each phase ships a testably better app. Phases 0–2 are fixes to the current
architecture (no rebuild needed — the bones are sound); Phase 3 is the structural refactor;
Phases 4–5 are packaging and the safety net. Rough sizing assumes AI-agent-assisted
development.

### Phase 0 — Security & data-safety hotfixes (do first; ~1–2 days)

1. **Lock down the local API** (C2/P1/P2): WS origin allowlist + per-launch shared secret
   (Tauri generates → sidecar env → webview via IPC → header/first-WS-message) + Host
   validation middleware. Bind explicitly to `127.0.0.1`.
2. **SQLite pragmas** (C8/P4): WAL, `busy_timeout=5000`, `synchronous=NORMAL` in the
   existing connect listener.
3. **Message `seq` column** (C7/A7): migration + order by it; stop relying on 1-second
   timestamp ties.
4. **Approval idempotency** (C4/A5): commit "executing" state before `execute_pending_action`,
   commit cleared state after; block re-approval of an executing action.
5. **Groq `usage or 0` guard** (A14) and **seed-failure loud-fail or lazy-reseed** (P5) —
   two one-liners that each kill a class of mystery failures.

### Phase 1 — Reliability of the core loop (~1 week)

6. **Real cancellation** (C1/A1/A2): per-session `asyncio.Task` for turns; free WS read
   loop; cancel checks per iteration and before each tool; drain/close provider stream and
   record usage on cancel (A10); persist partial assistant text with an `interrupted`
   marker (A9, with `try/finally` cleanup of contextvar + cancel key).
7. **Per-session turn lock** (A3): in-memory `asyncio.Lock` dict; reject/queue concurrent
   messages for the same session.
8. **Pending-action list + paused-turn guardrails** (C4/A4/A6): list-valued staging, one
   pause per action, rewrite *all* matching staged tool results, block side-effecting tools
   while paused, lenient review-response classification.
9. **Provider-neutral error taxonomy + bounded retry** (A15): map auth / rate-limit /
   context-too-long / malformed-tool-call across all three SDKs to actionable WS error
   codes; retry 429/5xx with backoff; replace the silent MAX_TOOL_ITERATIONS exit with a
   final no-tools summarization call (A11).
10. **Context-window management** (C5/A8): token-estimate per message
    (`token_count_estimate`), sliding window with budget per model (registry already has
    context sizes), then proper compaction (summarize + `is_compacted`) as a follow-up.
11. **Per-tool timeouts + structured results** (A23): `asyncio.wait_for` with
    category budgets; return `(ok, output)` instead of the `startswith("Error")` protocol
    (update `session_engine.py:733` accordingly).

### Phase 2 — Frontend stuck-states & desktop UX (~1 week)

12. **Streaming state machine hardening** (C3/F1/F2/F3/F11/F12/F13/F21): finalize all
    in-flight sessions on `onclose`; resync on reconnect; turn-generation counter to kill
    the refetch race; `AbortSignal.timeout` on every fetch; fix `disconnect()` timer/handler
    leaks; preserve cost on error paths; roll back/mark-failed optimistic messages with a
    retry affordance.
13. **Fix desktop-dead links** (F4): a shared `ExternalLink` that calls `openExternal`;
    use it for all doc links and as the ReactMarkdown `a` component. Scope the Tauri opener
    capability to an allowlist (F19).
14. **Onboarding/boot robustness** (F5/F6/F9/F17): surface `completeOnboarding` failures
    instead of navigating; treat already-configured providers as advanceable in the wizard;
    handle `CommandEvent::Terminated` in the shell (log, one respawn, emit event the
    BootGate can show); BootGate on /settings (or proper error states in SettingsApp);
    soften the 60s boot ceiling into a "still starting…" state.
15. **Clean shutdown + port strategy** (F8/F10/P9/T-port): Tauri picks a free port, passes
    it to sidecar (env) and webview (IPC) — removes the compile-time 8000 constant;
    `tauri-plugin-single-instance`; SIGTERM-to-process-group with SIGKILL escalation;
    backend self-exits when orphaned (parent-PID watch); sidecar exits with a clear message
    on bind failure.
16. **Chat UX debt** (F15/F16/F20/F23): near-bottom-only autoscroll + jump-to-latest;
    session fetch loading/error states; tabbed right rail; session rename/delete UI (APIs
    exist); copy buttons; "stopped" indicator; seed header cost from the session record;
    unify chat onto the CSS-variable theme.
17. **CSP** (F7): set a real policy (`default-src 'self'; connect-src http://localhost:*
    ws://localhost:*; img-src 'self' data:; style-src 'self' 'unsafe-inline'`).

### Phase 3 — Architecture cleanup (~1 week, can interleave with 2)

18. **One LLM client to rule them all** (A31/A17/C6): extract neutral `llm_types.py`
    (StreamChunk/StreamResult/ToolCall); one shared OpenAI-compatible streaming
    implementation parameterized by base_url/key (Groq + OpenAI + Google's OpenAI-compat
    endpoint), with the native genai client as the only special case; registry becomes the
    single source of provider truth; fallback = any available configured model; loud error
    when no provider is configured.
19. **Fix or gate the Gemini 3.x path** (A12/A13): integration-test `google_genai_client`
    (schema sanitization, grouped function responses, persisted thought signatures) before
    the registry advertises those models; until then, hide them.
20. **Registry/pricing hygiene** (A18/A21/A19/A20): reconcile model IDs and pricing in one
    table; live `/models` validation in Settings; derive `HEAVY_SLASH_COMMANDS` from
    `load_skills()`; update or drop `Session.llm_provider/llm_model`.
21. **Single-workspace data model** (P8/P7/P10/P6): collapse org/user resolution behind one
    `get_workspace()` helper (keep tables, kill the join-chase and `LEGACY_*` paths), add
    `ondelete="CASCADE"` FKs, drop `organizations.llm_api_keys`, store timezone-aware UTC.
22. **Engine polish** (A22/A24/A25/A26/A29/A30/P12): advance or drop `active_skill_phase`;
    portable strftime; prompt reflects actual providers/search config; clean AwaitReview
    tool output; reject empty post-strip messages; serialize WS events through the pydantic
    schemas; guard the WS read loop against malformed frames.
23. **Vault key → macOS Keychain** (P3): `keyring` with the file as fallback (and the
    fallback `chmod 600`).
24. **Memory improvements** (A28/A32): slug-collision suffixing, file-write-after-commit,
    and opt-in post-conversation memory extraction.

### Phase 4 — Packaging & Apple Silicon (~3–5 days)

25. **Honest multi-arch build** (C9/T9/T10): derive `TARGET_TRIPLE` from `rustc -vV`; pass
    `--target` to `tauri build`; document that PyInstaller must run per-arch; then either
    ship two DMGs or `lipo` a universal sidecar + `universal-apple-darwin` Tauri target.
26. **Reproducible builds** (T11/T12): Python lockfile consumed by `build-desktop.sh`;
    replace `collect_submodules("google")` with explicit subpackages + `copy_metadata`;
    extend `--selfcheck` with alembic-against-temp-SQLite and Google SDK import checks.
27. **Signing path** (T13): switch PyInstaller to onedir, then Developer ID signing +
    notarization (also fixes the slow one-file cold start).
28. **Housekeeping**: remove `ureq`, `bundle.android`, placeholder Cargo metadata; single
    version source synced by a release script.

### Phase 5 — Test pyramid, CI, docs (~1 week, start alongside Phase 1)

29. **The big one — engine integration tests** (T1): stub `llm.stream_message` with
    scripted chunk/result sequences and drive `process_message` against the SQLite fixture,
    covering: plain turn; tool-call turn; AwaitReview pause + approve/revise/restart incl.
    `_rewrite_staged_tool_result`; pending-action pause + approve-executes (stubbed Google);
    cancel mid-stream; commit failure. Port and delete `try_pause`, `try_pause_action`,
    `try_tool_loop`, `try_credentials`, `try_documents`, `try_memory`.
30. **Contract tests** (T2/T5): WS event JSON shapes via TestClient (this is the de-facto
    frontend API); httpx ASGI tests for sessions/onboarding/connections/preferences.
31. **Unit fill-ins** (T3/T4): vault encrypt/decrypt incl. rotated-key fallback;
    `Settings`/DATA_DIR precedence and vault-key minting against `tmp_path`;
    `_history_to_llm_messages`; `execute_tool` error contract; memory-store round-trip.
32. **CI overhaul** (T6/T14): frontend job (`npm ci && tsc --noEmit && next build`) +
    committed ESLint flat config; ruff for the backend; a `DATA_DIR` matrix leg; a
    `macos` job that freezes the sidecar and runs the extended `--selfcheck`; restrict
    push-triggered runs to main; drop the Postgres service from the SQLite leg.
33. **Docs rewrite** (T15/T16): README for the actual stack (SQLite, three providers,
    optional keys via onboarding, desktop build as the headline); INSTALL.md arch caveat;
    fix stale module docstrings and comments flagged above.

### Suggested order of execution

Phase 0 immediately (small, high-stakes). Then run Phase 1 and Phase 5's engine tests
*together* — writing the integration harness first makes every Phase 1 fix verifiable.
Phase 2 next (it's what testers feel). Phase 3 opportunistically as files are touched.
Phase 4 before the next distributed build. Total: roughly 4–5 focused weeks of
agent-assisted work.

### What does NOT need a rebuild

The skills system (SKILL.md loader), the tool registry, the OAuth flow, the alembic
migration set, the PyInstaller data bundling, and the overall Tauri-sidecar shape are all
sound — the review found no reason to replace them. The revamp is targeted surgery on the
loop's concurrency model, the provider abstraction, the frontend streaming state machine,
and the trust boundary of the local API — not a rewrite.
