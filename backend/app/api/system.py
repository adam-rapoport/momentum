"""Desktop-shell utility endpoints.

POST /system/open-url — open an external URL in the user's default browser
(or mail client for mailto:). Exists because the webview→Tauri IPC route for
URL-opening proved unreliable in packaged builds (invokes observed hanging
without a response, 2026-07-04) while the webview→backend HTTP channel is
exercised constantly and known-good. The backend is a regular process, so
macOS `open` / `webbrowser` work without any webview involvement.

Protected by the standard auth-token middleware (NOT exempt), so only the
app's own webview can call it. Scheme-allowlisted: this must never become a
run-anything endpoint.
"""
from __future__ import annotations

import subprocess
import sys
import webbrowser
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["system"])

_ALLOWED_SCHEMES = {"http", "https", "mailto"}


class OpenUrlPayload(BaseModel):
    url: str


@router.post("/open-url")
async def open_url(payload: OpenUrlPayload) -> dict:
    scheme = (urlparse(payload.url).scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=400, detail=f"scheme '{scheme}' not allowed")
    if sys.platform == "darwin":
        # Fire-and-forget; /usr/bin/open hands off to LaunchServices.
        subprocess.Popen(
            ["/usr/bin/open", payload.url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        webbrowser.open(payload.url)
    return {"opened": payload.url}
