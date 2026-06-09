from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.local_store import LocalKVStore

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Per-connection SQLite setup. Only registered for SQLite — the PRAGMAs would
# be invalid on Postgres.
#   foreign_keys: enforcement is OFF by default; turn it on so FK constraints
#     behave like Postgres.
#   journal_mode=WAL: readers don't block the writer. The app opens multiple
#     connections (per-request sessions + the WebSocket's own session), and
#     without WAL an overlapping REST write during a turn commit throws
#     "database is locked".
#   busy_timeout: when two writers do collide, wait up to 5s for the lock
#     instead of failing immediately.
#   synchronous=NORMAL: the recommended pairing with WAL — durable except
#     against power loss, much faster than FULL.
if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_setup(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# In-process replacement for Redis (cancel flags + OAuth state tokens).
# Single-process app, so an in-memory store is sufficient. See local_store.py.
kv_store = LocalKVStore()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_kv() -> LocalKVStore:
    return kv_store
