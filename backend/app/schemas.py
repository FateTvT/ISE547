from pydantic import BaseModel


class HelloResponse(BaseModel):
    message: str


class AIChatRequest(BaseModel):
    message: str | None = None
    session_id: str | None = None


class SessionResponse(BaseModel):
    id: str
    name: str


class SessionMessageResponse(BaseModel):
    role: str
    content: str


class SessionDetailResponse(BaseModel):
    id: str
    name: str
    messages: list[SessionMessageResponse]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
