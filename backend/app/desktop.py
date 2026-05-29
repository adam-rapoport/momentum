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

# Fixed loopback port. Kept at 8000 to match the frontend's default API/WS base
# and the registered Google OAuth redirect URI (localhost:8000/...). Changing it
# means also updating GOOGLE_REDIRECT_URI *and* the Google Cloud console
# redirect registration, or "Connect Google" breaks.
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


def main() -> None:
    # Honour an explicit DATA_DIR (e.g. set by the Tauri shell) if present,
    # otherwise fall back to the per-OS default. The directory itself is created
    # later by bootstrap_data_dir() in the app lifespan — single owner.
    data_dir = os.environ.get("DATA_DIR") or str(default_data_dir())
    os.environ["DATA_DIR"] = str(Path(data_dir).expanduser())

    # Import only AFTER DATA_DIR is set so app.config resolves paths against it.
    import uvicorn

    from app.main import app

    # log_config=None so uvicorn doesn't clobber our JSON logging (set up in the
    # app lifespan via configure_logging). Bind loopback only — never expose the
    # desktop backend on the network.
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_config=None)


if __name__ == "__main__":
    main()
