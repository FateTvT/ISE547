from pydantic import BaseModel


class HelloResponse(BaseModel):
    message: str


class AIChatRequest(BaseModel):
    message: str = ""
