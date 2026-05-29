# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the pMomentum desktop backend sidecar.

Build (from backend/, with the desktop extra installed):
    .venv/bin/pyinstaller pmomentum.spec --noconfirm

Produces a SINGLE-FILE executable at dist/pmomentum-backend that launches
app/desktop.py (uvicorn on 127.0.0.1:8000). One-file (not one-dir) so the Tauri
shell can use it directly as a sidecar `externalBin`. On launch it self-extracts
to a temp dir (sys._MEIPASS); module __file__ paths resolve there, so the
bundled data dirs below line up exactly as in the source tree.

Why each data dir is bundled — the app resolves these via `__file__` at
runtime, and PyInstaller sets module __file__ to paths under _internal/, so the
bundled layout must mirror the source layout:
  - alembic/        → read by app.main._run_migrations (script_location = backend/alembic)
  - app/prompts/    → app.core.system_prompt._STATIC_DIR
  - app/skills/     → app.core.skills._SKILLS_DIR
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = []
# uvicorn imports its protocol/loop implementations dynamically by string.
hiddenimports += collect_submodules("uvicorn")
# SQLAlchemy loads the dialect by name; aiosqlite is our default driver.
hiddenimports += collect_submodules("aiosqlite")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")
# Google SDKs (auth, oauth2, genai, api client) are namespace packages whose
# submodules aren't all statically reachable.
hiddenimports += collect_submodules("google")
hiddenimports += collect_submodules("googleapiclient")
# Our own package, so dynamically-referenced modules (tools, model clients,
# skills loader) are all present in the frozen app.
hiddenimports += collect_submodules("app")

datas = [
    ("alembic", "alembic"),
    ("app/prompts", "app/prompts"),
    ("app/skills", "app/skills"),
]
# trafilatura ships non-Python data (settings/model files) it reads at runtime,
# and pulls in justext (stoplist data) + courlan — collect their data too, or
# extraction crashes with FileNotFoundError on justext/stoplists.
datas += collect_data_files("trafilatura")
datas += collect_data_files("justext")
datas += collect_data_files("courlan")

a = Analysis(
    ["app/desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],  # not used; trims the bundle
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pmomentum-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # stdout/stderr visible in dev; Tauri spawns it windowless
)
