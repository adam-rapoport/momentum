# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the Momentum desktop backend sidecar.

Build (from backend/, with the desktop extra installed):
    .venv/bin/pyinstaller momentum.spec --noconfirm

Produces a SINGLE-FILE executable at dist/momentum-backend that launches
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
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

hiddenimports = []
# uvicorn imports its protocol/loop implementations dynamically by string.
hiddenimports += collect_submodules("uvicorn")
# SQLAlchemy loads the dialect by name; aiosqlite is our default driver.
hiddenimports += collect_submodules("aiosqlite")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")
# Google SDKs live in the `google` namespace package, so not every submodule is
# statically reachable. Collect ONLY the subpackages the app actually imports
# (verified against backend imports: google.oauth2.credentials in the
# integrations, google.genai in google_genai_client, google.auth transitively)
# — a bare collect_submodules("google") would also sweep in google.cloud,
# google.protobuf, google.logging etc. that nothing uses. google.api_core is
# statically imported by googleapiclient.discovery, so PyInstaller's analysis
# follows it on its own.
hiddenimports += collect_submodules("google.auth")
hiddenimports += collect_submodules("google.oauth2")
hiddenimports += collect_submodules("google.genai")
hiddenimports += collect_submodules("googleapiclient")
# reportlab (via xhtml2pdf, the v0.3 PDF exporter) loads its barcode widget
# modules dynamically by name at import time — the frozen build's selfcheck
# fails with ModuleNotFoundError: reportlab.graphics.barcode.code128 without
# this. Collect the whole barcode subpackage; it's small.
hiddenimports += collect_submodules("reportlab.graphics.barcode")
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
# Dist metadata for the Google SDKs so importlib.metadata.version() resolves
# inside the frozen app. Verified 2026-06: both packages hardcode __version__
# in version.py (no crash without this), but google.api_core's dependency
# checks consult dist metadata at runtime and fall back to "unknown" when it's
# missing — copying it (a few KB) keeps that path honest.
datas += copy_metadata("google-api-python-client")
datas += copy_metadata("google-genai")

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
    name="momentum-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # stdout/stderr visible in dev; Tauri spawns it windowless
)
