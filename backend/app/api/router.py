from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.integrations import router as integrations_router
from app.api.memory import router as memory_router
from app.api.preferences import router as preferences_router
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(sessions_router)
api_router.include_router(memory_router)
api_router.include_router(documents_router)
api_router.include_router(integrations_router)
api_router.include_router(preferences_router)

ws_router = websocket_router
