import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router, ws_router
from app.config import bootstrap_data_dir, settings
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


def _run_migrations() -> None:
    """Bring the database schema to head via Alembic's Python API.

    Uses the API rather than the `alembic` CLI so it works inside a frozen
    desktop binary (no CLI on PATH). Paths are resolved relative to this file,
    so it's independent of the working directory. Must run in a worker thread:
    alembic/env.py calls asyncio.run() internally, which raises if invoked from
    an already-running event loop (the lifespan's).

    We deliberately build a Config WITHOUT pointing at alembic.ini: that file's
    presence makes env.py call fileConfig(), which (disable_existing_loggers=True)
    silences our app loggers and replaces the JSON formatter with a plain one for
    the rest of the process. Skipping it leaves our configure_logging() intact.
    env.py sets sqlalchemy.url itself from settings, so the only option we must
    supply is the script location.
    """
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent  # backend/
    cfg = Config()
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        logger.info("Sentry crash reporting enabled")
    # Create the per-user data dir + mint the credential vault key if needed
    # (no-op for web dev, where DATA_DIR is unset). Must precede the migration
    # below, which opens/creates the SQLite file inside that dir.
    bootstrap_data_dir()
    # Self-heal the schema on startup for the self-contained SQLite DB (desktop
    # + local dev): first run creates the file and applies every migration;
    # later runs are a no-op (Alembic skips applied revisions). Postgres is left
    # to a deliberate `alembic upgrade head` so an operator controls when
    # migrations run against a shared DB. A failed migration must NOT boot onto
    # a broken schema, so this fails loudly (unlike the best-effort refresh below).
    if engine.dialect.name == "sqlite":
        try:
            await asyncio.to_thread(_run_migrations)
        except Exception:
            logger.exception("startup: database migration failed")
            raise
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
    # Local web-dev origins PLUS the Tauri desktop webview, which serves the app
    # from a custom scheme: tauri://localhost (macOS/Linux) and
    # http://tauri.localhost (Windows).
    allow_origin_regex=r"(tauri://localhost|http://tauri\.localhost|http://(localhost|127\.0\.0\.1)(:\d+)?)",
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
