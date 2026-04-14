"""Database thread model for conversation persistence."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Thread(SQLModel, table=True):
    """Thread model for storing conversation threads."""

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
