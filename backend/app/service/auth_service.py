"""Authentication service for JWT and users."""

from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from sqlmodel import Session, select

from app.core.config import settings
from app.models.user import User
from app.schemas import UserResponse


class AuthService:
    """Provide login and token verification methods."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_access_token(self, user: User) -> str:
        """Create a signed JWT access token."""

        expires_at = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    async def login(self, username: str, password: str) -> str | None:
        """Validate username/password and return access token."""

        statement = select(User).where(User.username == username)
        user = self.session.exec(statement).first()
        if not user:
            return None
        if not user.verify_password(password):
            return None
        return self.create_access_token(user)

    async def get_current_user(self, token: str) -> UserResponse | None:
        """Decode token and load current user."""

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            user_id = payload.get("sub")
            if not user_id:
                return None
        except InvalidTokenError:
            return None

        user = self.session.get(User, int(user_id))
        if not user:
            return None
        return UserResponse(
            id=user.id or 0, username=user.username or "", email=user.email
        )


async def init_default_user(session: Session) -> None:
    """Create default user when missing."""

    statement = select(User).where(User.username == "ISE547")
    existing = session.exec(statement).first()
    if existing:
        return

    user = User(
        email="ise547@example.com",
        username="ISE547",
        hashed_password=User.hash_password("zkj666"),
    )
    session.add(user)
    session.commit()
