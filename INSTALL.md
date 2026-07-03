# Installing Momentum (Mac test build)

This is the **internal test build** of the Momentum desktop app: unsigned, and
built **for the architecture of the Mac that runs the build script** — there is
no cross-compilation:

- Built on an **Intel Mac** → an `x86_64` build. It also runs on Apple Silicon
  Macs through Apple's Rosetta translation layer.
- Built on an **Apple Silicon Mac** → a native `aarch64` (arm64) build. It will
  **not** run on Intel Macs.

The `.dmg` filename carries the real architecture (`_x64` / `_aarch64`), so you
always know what you built. It is meant for your own testing — not a public
release yet. Code signing, notarization, a universal (dual-arch) build, and a
public download come in later sprints.

---

## 1. Build it

From the project root (`momentum/`):

```bash
./build-desktop.sh
```

When it finishes, the installer is here (`<triple>` is your machine's Rust
target triple, e.g. `aarch64-apple-darwin` on Apple Silicon or
`x86_64-apple-darwin` on Intel; `<arch>` is `aarch64` or `x64` accordingly):

```
frontend/src-tauri/target/<triple>/release/bundle/dmg/Momentum_0.1.0_<arch>.dmg
```

(The raw app, if you want it directly, is alongside it at
`frontend/src-tauri/target/<triple>/release/bundle/macos/Momentum.app`.)

## 2. Install it

1. Double-click the `.dmg` to open it.
2. In the window that appears, **drag the Momentum icon onto the Applications
   folder**.
3. Eject the disk image (drag it to the Trash / click the eject button).

Momentum now lives in your Applications folder like any other Mac app.

## 3. First launch — the one-time security prompt

Because this build isn't signed by Apple yet, macOS will warn you the first time
you open it. **This is expected.** Here's how to get past it:

- **If you built and are running it on the same Mac:** it usually just opens. If
  not, follow the steps below.
- **If you copied the `.dmg` to another Mac** (downloaded, AirDropped, USB), macOS
  flags it. Do this:
  1. Open Momentum from Applications. You'll see a message like *"Momentum
     cannot be opened because Apple cannot check it for malicious software."*
     Click **Done** (do **not** click "Move to Trash").
  2. Open **System Settings → Privacy & Security**.
  3. Scroll down to the **Security** section. You'll see *"Momentum was blocked
     from use..."* with an **Open Anyway** button. Click it.
  4. Confirm with Touch ID / your password. Momentum launches.

You only have to do this **once** per Mac.

> If you instead see *"Momentum is damaged and can't be opened"*, that's macOS
> being extra strict about the unsigned download. Clear the quarantine flag once
> in Terminal, then open it normally:
> ```bash
> xattr -cr /Applications/Momentum.app
> ```

## 4. First-run setup

On first launch Momentum opens an **onboarding wizard**. Use it to:

- Pick a model and paste an API key for the **fast** slot (casual chat, tool
  calls) and the **drafting** slot (PRDs, updates) — any supported provider
  works for either: Groq, Google AI Studio, or OpenAI. Keys are stored
  **encrypted on your Mac** — they never leave the machine except to call the
  providers you entered them for.
- Optionally tell it about yourself and your product so the agent has context
  from message one.

Web search (Tavily / Perplexity) and the Google connection (Docs / Gmail /
Calendar) can be added afterwards in the in-app **Settings**, where you can
also change everything above.

## 5. Where your data lives

Everything Momentum stores lives in one folder:

```
~/Library/Application Support/Momentum/
├── momentum.db      # your sessions, memory, preferences (SQLite)
├── vault.key         # encrypts your saved API keys
└── memory/           # memory + document files
```

To start completely fresh, quit the app and delete that folder.

## 6. Updating

There's no auto-updater yet. To get a newer build, re-run `./build-desktop.sh`,
then reinstall the new `.dmg` over the old app (drag to Applications, replace).
Your data in `Application Support/Momentum` is kept across updates.

---

## Troubleshooting

- **Window never appears / hangs on launch:** the app waits for its bundled
  backend to come up on port **8000**. Make sure nothing else is using that port
  (e.g. a `uvicorn ... --reload` dev server). Quit the other process and relaunch.
- **"unidentified developer" every launch:** see step 3 — the *Open Anyway* path
  clears it for good; double-clicking before doing that does not.
- **Quitting:** use ⌘Q or close the window. The app shuts its backend down with
  it — nothing should be left running on port 8000 afterward.
