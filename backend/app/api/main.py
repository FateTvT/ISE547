from fastapi import APIRouter
from app.api.routes import ai_chat
from app.api.routes import hello

api_router = APIRouter()


api_router.include_router(hello.router, prefix="/hello", tags=["hello"])
api_router.include_router(ai_chat.router, prefix="/ai-chat", tags=["ai-chat"])
