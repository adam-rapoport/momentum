# Installing Momentum (macOS)

Momentum ships as a signed, notarized Mac app in two builds — pick the one for
your machine:

- **Apple Silicon** (M-series Macs): `Momentum_macOS_AppleSilicon.dmg`
  (also listed as `Momentum_<version>_aarch64.dmg` — same file)
- **Intel**: `Momentum_macOS_Intel.dmg`
  (also listed as `Momentum_<version>_x64.dmg` — same file)

Not sure which you have?  → Apple menu → *About This Mac*. "Chip: Apple M…"
means Apple Silicon; "Processor: Intel…" means Intel. (The Apple Silicon build
does not run on Intel Macs; the Intel build runs on Apple Silicon via Rosetta,
but the native build is faster.)

## 1. Install

1. Download the `.dmg` for your chip from the
   [latest release](https://github.com/adam-rapoport/momentum/releases/latest).
2. Double-click it, then **drag the Momentum icon onto the Applications folder**.
3. Eject the disk image and launch Momentum from Applications.

That's it — the app is signed and notarized by Apple, so there are no security
warnings to click through.

## 2. First-run setup

On first launch Momentum opens an **onboarding wizard**. Use it to:

- Pick a model and paste an API key for the **fast** slot (casual chat, tool
  calls) and the **drafting** slot (PRDs, updates) — any supported provider
  works for either: Google AI Studio, Groq, OpenAI, Anthropic, OpenRouter,
  Mistral, or a local Ollama server. Keys are stored **encrypted on your Mac**
  — they never leave the machine except to call the providers you entered them
  for.
- Optionally tell it about yourself and your product so the agent has context
  from message one.

Web search (Tavily / Perplexity) can be added afterwards in the in-app
**Settings**, where you can also change everything above.

## 3. Where your data lives

Everything Momentum stores lives in one folder:

```
~/Library/Application Support/Momentum/
├── momentum.db       # your sessions, memory, preferences (SQLite)
└── memory/           # memory + document files
```

The key that encrypts your saved API keys lives in the **macOS Keychain**
(item "Momentum"). To start completely fresh, quit the app and delete the
folder above.

## 4. Updating

Momentum updates itself: on launch it checks the latest release, and if a
newer version exists it asks — *Update now / Later*. Nothing installs without
your click. You can always install a newer `.dmg` over the old app manually
instead; your data is kept either way.

---

## Upgrading from an unsigned test build (pre-v0.1.0)

If you previously installed an unsigned pMomentum/Momentum test build:

1. Install the new Momentum app over the old one (if the old app is named
   **pMomentum**, delete it from Applications after installing Momentum).
2. On first launch, your data folder and database are migrated automatically —
   sessions, memories, and documents carry over.
3. macOS will show a **one-time Keychain prompt** (the new signature asks to
   read the key the old build stored). Enter your Mac password and click
   **Always Allow** — you'll never see it again.

## Building from source

From the project root: `./build-desktop.sh` builds an installer for your
machine's architecture at
`frontend/src-tauri/target/<triple>/release/bundle/dmg/`. Source builds are
unsigned — macOS will require System Settings → Privacy & Security → **Open
Anyway** on first launch.

## Troubleshooting

- **Window never appears / hangs on launch:** the app waits for its bundled
  backend. If another process holds port **8000** (e.g. a `uvicorn ... --reload`
  dev server), Momentum picks a free port automatically — but if the app still
  hangs, quit the other process and relaunch.
- **Closing vs quitting:** closing the window (red button) keeps Momentum
  running in the background — it stays in the Dock and as a **≫ icon in the
  menu bar**, so reopening is instant and scheduled work can keep running.
  Click the Dock icon or the menu-bar icon to bring the window back. To fully
  quit, press **⌘Q** or pick **Quit Momentum** from the menu-bar icon; that
  shuts the backend down with it — nothing is left running afterward.
