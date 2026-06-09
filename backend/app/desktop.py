"""Programmatic entrypoint for running pMomentum as a self-contained desktop
backend. This is also the future PyInstaller freeze target.

It resolves a per-user, writable data directory and exports it as ``DATA_DIR``
*before* importing the app, so ``app.config`` roots the SQLite DB, the
memory/documents folders, and the credential vault key under it (see
``Settings._apply_data_dir``). It then serves the FastAPI app on a fixed
loopback port.

The web-dev workflow (``uvicorn app.main:app --reload``) is unaffected — this is
an *additional* front door, not a replacement. Run it with::

    python -m app.desktop
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Default loopback port. 8000 matches the frontend's default API/WS base and the
# registered Google OAuth redirect URI (localhost:8000/...). Overridable via
# PMOMENTUM_PORT, but note: changing it means also updating GOOGLE_REDIRECT_URI
# *and* the Google Cloud console redirect registration, or "Connect Google"
# breaks.
PORT = 8000
APP_NAME = "pMomentum"


def default_data_dir() -> Path:
    """The per-OS, per-user writable folder for the app's data."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA")
        return (Path(base) if base else home / "AppData" / "Roaming") / APP_NAME
    # Linux / other: respect XDG_DATA_HOME if set.
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else home / ".local" / "share") / APP_NAME


def _selfcheck() -> int:
    """Validate that the bundled dependencies + data files actually work inside
    the frozen binary. Run with `pmomentum-backend --selfcheck`. Returns a
    non-zero exit code on any failure. Useful as a smoke test of every build —
    catches PyInstaller omitting a data dir or a native dep before we ship.
    """
    import shutil
    import tempfile

    # The migration check boots the app's config against a throwaway SQLite
    # file. The env var must be set BEFORE the first `app.*` import in this
    # process (app.config builds its settings singleton at import time, and
    # an os.environ value beats any .env file).
    tmpdir = Path(tempfile.mkdtemp(prefix="pmomentum-selfcheck-"))
    selfcheck_db = tmpdir / "selfcheck.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{selfcheck_db.as_posix()}"

    ok = True

    def check(name: str, fn) -> None:
        nonlocal ok
        try:
            fn()
            print(f"  [ok]   {name}")
        except Exception as e:  # noqa: BLE001 — we report every failure, not just the first
            ok = False
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")

    def _crypto() -> None:
        from cryptography.fernet import Fernet

        f = Fernet(Fernet.generate_key())
        assert f.decrypt(f.encrypt(b"pm")) == b"pm"

    def _trafilatura() -> None:
        import trafilatura

        # Return value may be None for trivial input; we only need it to run.
        trafilatura.extract("<html><body><article><p>body text</p></article></body></html>")

    def _prompts() -> None:
        from app.core.system_prompt import _STATIC_DIR

        assert list(_STATIC_DIR.glob("*.md")), f"no prompt files under {_STATIC_DIR}"

    def _skills() -> None:
        from app.core.skills import _SKILLS_DIR

        assert list(_SKILLS_DIR.glob("*/SKILL.md")), f"no SKILL.md under {_SKILLS_DIR}"

    def _migrations() -> None:
        # Runs the real startup migration path (alembic Python API, bundled
        # alembic/ scripts) against the temp DB set up above. Catches a build
        # that omitted the migration scripts or an alembic/SQLAlchemy module.
        from app.main import _run_migrations

        _run_migrations()
        assert selfcheck_db.exists() and selfcheck_db.stat().st_size > 0, (
            f"migrations ran but produced no DB at {selfcheck_db}"
        )

    def _google_genai_sdk() -> None:
        from google import genai
        from google.genai import types

        assert genai.Client is not None and types.GenerateContentConfig is not None

    def _openai_sdk() -> None:
        import openai

        assert openai.AsyncOpenAI is not None

    def _google_api_client() -> None:
        import googleapiclient.discovery
        from google.oauth2.credentials import Credentials

        assert googleapiclient.discovery.build is not None and Credentials is not None

    try:
        check("cryptography Fernet round-trip", _crypto)
        check("trafilatura import + extract", _trafilatura)
        check("bundled prompts/static readable", _prompts)
        check("bundled skills readable", _skills)
        check("alembic migrations against temp SQLite", _migrations)
        check("google-genai SDK importable", _google_genai_sdk)
        check("openai SDK importable", _openai_sdk)
        check("google-api-python-client + oauth importable", _google_api_client)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("selfcheck:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())

    # Honour an explicit DATA_DIR (e.g. set by the Tauri shell) if present,
    # otherwise fall back to the per-OS default. The directory itself is created
    # later by bootstrap_data_dir() in the app lifespan — single owner.
    data_dir = os.environ.get("DATA_DIR") or str(default_data_dir())
    os.environ["DATA_DIR"] = str(Path(data_dir).expanduser())

    port = int(os.environ.get("PMOMENTUM_PORT", PORT))

    # Import only AFTER DATA_DIR is set so app.config resolves paths against it.
    import uvicorn

    from app.main import app

    # log_config=None so uvicorn doesn't clobber our JSON logging (set up in the
    # app lifespan via configure_logging). Bind loopback only — never expose the
    # desktop backend on the network.
    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)


if __name__ == "__main__":
    main()
