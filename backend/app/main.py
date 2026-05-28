import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router, ws_router
from app.config import settings
from app.core.integrations import google_oauth
from app.dependencies import SessionLocal, engine, redis_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Proactively refresh near-expiry Google OAuth tokens at startup so the
    # first integration call of the session doesn't fail mid-task. Best-effort:
    # never block or crash startup on this.
    try:
        async with SessionLocal() as db:
            processed = await google_oauth.refresh_expiring_tokens(db)
        if processed:
            logger.info("startup: refreshed/checked %d Google integration(s)", processed)
    except Exception as e:  # noqa: BLE001 — startup must not fail on a refresh hiccup
        logger.warning("startup Google token refresh pass skipped: %s", e)
    yield
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="pMomentum", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    status: dict[str, str] = {"status": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["status"] = "degraded"
        status["database"] = f"error: {type(e).__name__}"

    try:
        pong = await redis_client.ping()
        status["redis"] = "ok" if pong else "error"
    except Exception as e:
        status["status"] = "degraded"
        status["redis"] = f"error: {type(e).__name__}"

    return status
