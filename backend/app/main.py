import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models  # noqa: F401
from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine
from app.service.auth_service import init_default_user
from sqlmodel import SQLModel, Session
import uvicorn

app = FastAPI()
logging.getLogger("app").setLevel(logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return service health status."""

    return {"status": "ok"}


@app.on_event("startup")
async def startup() -> None:
    """Initialize database tables and default user."""

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        await init_default_user(session)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
        reload_dirs=["app"],
    )
