from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router, ws_router
from app.config import settings
from app.dependencies import engine, redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
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
