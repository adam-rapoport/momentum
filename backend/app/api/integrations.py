"""Integrations REST API — Sprint 3 Chunk D (Google Docs).

Endpoints:
  GET  /api/v1/integrations/google/status    — is it connected? email?
  POST /api/v1/integrations/google/connect   — returns { authorize_url }
  GET  /api/v1/integrations/google/callback  — OAuth redirect target
  DELETE /api/v1/integrations/google         — disconnect

The callback is not a JSON API — it's the URL Google redirects the user's
browser to. We finish the token exchange and then render a small self-contained
HTML page telling the user to return to pMomentum. (We deliberately do NOT
redirect to a frontend route: in the desktop build the UI is served from a
Tauri internal protocol, not an http origin, so there is no reachable
`FRONTEND_ORIGIN/settings` page. The app re-checks Google status when its window
regains focus, so the card updates on its own once the user comes back.)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import get_default_user
from app.core.integrations.google_oauth import (
    OAuthFlowError,
    OAuthNotConfigured,
    complete_authorization,
    disconnect,
    get_integration,
    integration_public_view,
    start_authorization,
)
from app.core.integrations.vault import VaultNotConfigured
from app.core.local_store import LocalKVStore
from app.dependencies import get_db, get_kv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/google/status")
async def google_status(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    integration = await get_integration(db, user.id)
    return integration_public_view(integration)


@router.post("/google/connect")
async def google_connect(
    db: AsyncSession = Depends(get_db),
    kv: LocalKVStore = Depends(get_kv),
) -> dict:
    user = await get_default_user(db)
    try:
        authorize_url = await start_authorization(kv, user.id)
    except OAuthNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except VaultNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {"authorize_url": authorize_url}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    kv: LocalKVStore = Depends(get_kv),
):
    """Google redirects the browser here with ?code=...&state=... (or error=...).
    We complete the exchange and render a self-contained 'return to pMomentum'
    page (see module docstring for why we don't redirect to the frontend)."""
    error = request.query_params.get("error")
    if error:
        return _result_page(
            ok=False,
            message=f"Google reported an error: {error}. Nothing was changed — you can close this tab and try again.",
        )

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return _result_page(
            ok=False,
            message="The login didn't return the expected information. Please close this tab and try connecting again.",
        )

    try:
        await complete_authorization(db, kv, code, state)
    except (OAuthFlowError, OAuthNotConfigured, VaultNotConfigured) as e:
        logger.warning("google oauth callback failed: %s", e)
        return _result_page(
            ok=False,
            message="We couldn't finish connecting your Google account. Please close this tab and try again.",
        )

    return _result_page(
        ok=True,
        message="Your Google account is connected. You can close this tab and return to pMomentum.",
    )


def _result_page(ok: bool, message: str) -> HTMLResponse:
    """A tiny, dependency-free HTML page shown in the user's browser after the
    Google OAuth round-trip. Works for both the desktop build (system browser)
    and web dev — it relies on no frontend route."""
    accent = "#16a34a" if ok else "#dc2626"
    icon = "✓" if ok else "✕"
    title = "Connected" if ok else "Couldn't connect"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>pMomentum · {title}</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         background:#f7f7f8; color:#1a1a1a; }}
  .card {{ background:#fff; border:1px solid #e5e5e5; border-radius:14px; padding:32px 36px;
           max-width:420px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
  .badge {{ width:48px; height:48px; border-radius:50%; display:inline-flex; align-items:center;
            justify-content:center; font-size:24px; color:#fff; background:{accent}; margin-bottom:16px; }}
  h1 {{ font-size:18px; margin:0 0 8px; }}
  p {{ font-size:14px; line-height:1.5; color:#555; margin:0 0 20px; }}
  button {{ font-size:14px; padding:9px 18px; border-radius:8px; border:1px solid #d4d4d4;
            background:#fff; cursor:pointer; }}
</style>
</head>
<body>
  <div class="card">
    <div class="badge">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <button onclick="window.close()">Close this tab</button>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@router.delete("/google", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(db: AsyncSession = Depends(get_db)) -> None:
    user = await get_default_user(db)
    await disconnect(db, user.id)
