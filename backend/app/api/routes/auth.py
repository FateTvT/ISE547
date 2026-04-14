"""Auth endpoints for login and session verification."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.auth import get_auth_service, get_verified_session
from app.schemas import LoginRequest, TokenResponse, UserResponse
from app.service.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Issue JWT token after validating credentials."""

    access_token = await auth_service.login(payload.username, payload.password)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: UserResponse = Depends(get_verified_session),
) -> UserResponse:
    """Get current verified user."""

    return current_user
