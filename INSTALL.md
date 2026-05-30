# Installing pMomentum (Mac test build)

This is the **internal test build** of the pMomentum desktop app: unsigned, built
for **Intel Macs** (it also runs on Apple Silicon Macs through Apple's Rosetta
translation layer). It is meant for your own testing — not a public release yet.
Code signing, notarization, an Apple Silicon build, and a public download come in
later sprints.

---

## 1. Build it

From the project root (`pmomentum/`):

```bash
./build-desktop.sh
```

When it finishes, the installer is here:

```
frontend/src-tauri/target/release/bundle/dmg/pMomentum_0.1.0_x64.dmg
```

(The raw app, if you want it directly, is alongside it at
`frontend/src-tauri/target/release/bundle/macos/pMomentum.app`.)

## 2. Install it

1. Double-click the `.dmg` to open it.
2. In the window that appears, **drag the pMomentum icon onto the Applications
   folder**.
3. Eject the disk image (drag it to the Trash / click the eject button).

pMomentum now lives in your Applications folder like any other Mac app.

## 3. First launch — the one-time security prompt

Because this build isn't signed by Apple yet, macOS will warn you the first time
you open it. **This is expected.** Here's how to get past it:

- **If you built and are running it on the same Mac:** it usually just opens. If
  not, follow the steps below.
- **If you copied the `.dmg` to another Mac** (downloaded, AirDropped, USB), macOS
  flags it. Do this:
  1. Open pMomentum from Applications. You'll see a message like *"pMomentum
     cannot be opened because Apple cannot check it for malicious software."*
     Click **Done** (do **not** click "Move to Trash").
  2. Open **System Settings → Privacy & Security**.
  3. Scroll down to the **Security** section. You'll see *"pMomentum was blocked
     from use..."* with an **Open Anyway** button. Click it.
  4. Confirm with Touch ID / your password. pMomentum launches.

You only have to do this **once** per Mac.

> If you instead see *"pMomentum is damaged and can't be opened"*, that's macOS
> being extra strict about the unsigned download. Clear the quarantine flag once
> in Terminal, then open it normally:
> ```bash
> xattr -cr /Applications/pMomentum.app
> ```

## 4. First-run setup

On first launch pMomentum opens an **onboarding wizard**. Use it to:

- Enter your API keys (Groq is required; Google AI Studio for heavy drafting;
  Tavily for web search). Keys are stored **encrypted on your Mac** — they never
  leave the machine except to call the providers you entered them for.
- Optionally connect Google (Docs / Gmail / Calendar) and set your name/workspace.

You can change all of this later in the in-app **Settings**.

## 5. Where your data lives

Everything pMomentum stores lives in one folder:

```
~/Library/Application Support/pMomentum/
├── pmomentum.db      # your sessions, memory, preferences (SQLite)
├── vault.key         # encrypts your saved API keys
└── memory/           # memory + document files
```

To start completely fresh, quit the app and delete that folder.

## 6. Updating

There's no auto-updater yet. To get a newer build, re-run `./build-desktop.sh`,
then reinstall the new `.dmg` over the old app (drag to Applications, replace).
Your data in `Application Support/pMomentum` is kept across updates.

---

## Troubleshooting

- **Window never appears / hangs on launch:** the app waits for its bundled
  backend to come up on port **8000**. Make sure nothing else is using that port
  (e.g. a `uvicorn ... --reload` dev server). Quit the other process and relaunch.
- **"unidentified developer" every launch:** see step 3 — the *Open Anyway* path
  clears it for good; double-clicking before doing that does not.
- **Quitting:** use ⌘Q or close the window. The app shuts its backend down with
  it — nothing should be left running on port 8000 afterward.
