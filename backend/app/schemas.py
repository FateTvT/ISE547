from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AIChatStreamEventType(str, Enum):
    MESSAGE = "message"
    ERROR = "error"
    INTERRUPT = "interrupt"


class HelloResponse(BaseModel):
    message: str


class AIChatRequest(BaseModel):
    message: str | None = None
    session_id: str | None = None
    resume: str | None = None
    age: int = Field(default=30, ge=0, le=100)
    sex: str = "undefine"

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, value: str) -> str:
        """Validate allowed sex values for diagnosis state."""

        normalized = value.strip().lower()
        if normalized not in {"male", "female", "undefine"}:
            raise ValueError("sex must be one of: male, female, undefine")
        return normalized


class QuestionChoice(BaseModel):
    choice_id: str
    choice: str
    selected: bool


class QuestionCard(BaseModel):
    question: str
    question_choices: list[QuestionChoice]


class SessionResponse(BaseModel):
    id: str
    name: str


class SessionMessageResponse(BaseModel):
    role: str
    content: str


class SessionChoiceResponse(BaseModel):
    choice_id: str
    question_card: QuestionCard | None = None


class SessionDetailResponse(BaseModel):
    id: str
    name: str
    messages: list[SessionMessageResponse]
    user_choices: list[SessionChoiceResponse] = Field(default_factory=list)
    diagnosis_completed: bool = False


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
