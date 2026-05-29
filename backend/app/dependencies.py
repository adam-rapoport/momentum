from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.local_store import LocalKVStore

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# SQLite ships with foreign-key enforcement OFF by default. Turn it on for
# every connection so ON DELETE / FK constraints behave like Postgres. Only
# registered for SQLite — the PRAGMA would be invalid on Postgres.
if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# In-process replacement for Redis (cancel flags + OAuth state tokens).
# Single-process app, so an in-memory store is sufficient. See local_store.py.
kv_store = LocalKVStore()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_kv() -> LocalKVStore:
    return kv_store
