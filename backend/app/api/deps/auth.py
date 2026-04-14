"""Authentication dependencies for API routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.db import get_session
from app.schemas import UserResponse
from app.service.auth_service import AuthService

security = HTTPBearer(auto_error=False)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """Build auth service from request session."""

    return AuthService(session)


async def api_verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Verify bearer token and return current user."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    token = credentials.credentials
    user = await auth_service.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    return user


async def get_verified_session(
    user: UserResponse = Depends(api_verify_token),
) -> UserResponse:
    """Provide verified user for protected endpoints."""

    return user
