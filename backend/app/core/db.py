"""Database engine and session dependencies."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings


def _sqlite_connect_args() -> dict:
    """Build sqlite connect args when needed."""

    if settings.DATABASE_URL.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(settings.DATABASE_URL, connect_args=_sqlite_connect_args())


def get_session() -> Generator[Session, None, None]:
    """Yield a database session."""

    with Session(engine) as session:
        yield session
