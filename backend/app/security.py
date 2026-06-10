"""Trust boundary for the local desktop backend.

The backend listens on 127.0.0.1 with no login, so the dangerous callers are
not remote hosts — they are *other things on this machine's browser*: any
website can fire requests at http://127.0.0.1:8000 (CORS only restricts
reading responses, not sending state-changing requests) and WebSockets are
not subject to CORS at all. DNS rebinding additionally defeats origin-based
reasoning for plain GETs. Defense is three layered checks:

1. Host allowlist — rejects DNS-rebinding requests, whose Host header is the
   attacker's domain even though the TCP connection is loopback.
2. Origin allowlist — rejects browser-initiated cross-site requests, which
   always carry the page's Origin. Requests with no Origin header (curl,
   the Python test client, server-to-server) are allowed; a local process
   needs no browser to attack us, so blocking it here buys nothing.
3. Shared auth token — the Tauri shell generates a per-launch secret, hands
   it to the sidecar via PMOMENTUM_AUTH_TOKEN and to the webview over IPC
   (`get_backend_token`). When set, every /api request must present it in
   the X-PMomentum-Token header and every WS connect in the `token` query
   param. Unset (web dev, pytest) the token check is skipped but checks
   1-2 still apply.

The Google OAuth callback is exempt from the token check: Google redirects
the user's real browser there, which cannot know the token. That endpoint is
protected by its own single-use state parameter.
"""
from __future__ import annotations

import hmac
import re

from app.config import settings

# Hosts a legitimate local client can address the backend as. "testserver" is
# Starlette's TestClient default. Matching is on the hostname only (port
# stripped), lowercase.
_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}

# Browser origins allowed to talk to us: local web dev on any port, plus the
# Tauri webview's custom scheme (tauri://localhost on macOS/Linux,
# http://tauri.localhost on Windows). Keep in sync with the CORS regex in
# app.main.
_ALLOWED_ORIGIN_RE = re.compile(
    r"^(tauri://localhost|http://tauri\.localhost|http://(localhost|127\.0\.0\.1)(:\d+)?)$"
)

# Paths exempt from the auth-token requirement (still subject to the Host and
# Origin checks). /health is the boot-gate poll; the OAuth callback arrives
# from the user's browser via Google's redirect and carries no token.
_TOKEN_EXEMPT_PREFIXES = (
    "/health",
    "/api/v1/integrations/google/callback",
)


def host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    host = host_header.strip().lower()
    # Strip a port suffix, careful with IPv6 bracket notation: "[::1]:8000".
    if host.startswith("["):
        host = host.split("]", 1)[0] + "]"
    elif ":" in host:
        host = host.rsplit(":", 1)[0]
    return host in _ALLOWED_HOSTS


def origin_allowed(origin_header: str | None) -> bool:
    """True when the request either has no Origin (non-browser client) or an
    Origin on the local allowlist."""
    if origin_header is None or origin_header == "":
        return True
    return bool(_ALLOWED_ORIGIN_RE.match(origin_header.strip()))


def token_required(path: str) -> bool:
    if not settings.auth_token:
        return False
    return not any(path.startswith(p) for p in _TOKEN_EXEMPT_PREFIXES)


def token_valid(presented: str | None) -> bool:
    expected = settings.auth_token
    if not expected:
        return True
    return hmac.compare_digest(presented or "", expected)
