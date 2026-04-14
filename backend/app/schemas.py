from pydantic import BaseModel


class HelloResponse(BaseModel):
    message: str


class AIChatRequest(BaseModel):
    message: str = ""
    session_id: str = "default-session"


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
