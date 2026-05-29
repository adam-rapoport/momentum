import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router, ws_router
from app.config import settings
from app.core.integrations import google_oauth
from app.dependencies import SessionLocal, engine
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)

# Optional crash reporting. Initialized before the app is created so the
# FastAPI integration instruments cleanly. No-op unless SENTRY_DSN is set —
# off by default so the app never phones home without the user opting in.
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,  # error reporting only; no perf tracing
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        logger.info("Sentry crash reporting enabled")
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

    return status
