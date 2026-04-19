from typing import Any

from pydantic import BaseModel, Field


class InfermedicaAge(BaseModel):
    value: int


class InfermedicaEvidence(BaseModel):
    id: str
    choice_id: str


class InfermedicaDiagnosisRequest(BaseModel):
    sex: str
    age: InfermedicaAge
    evidence: list[InfermedicaEvidence]


class InfermedicaParseRequest(BaseModel):
    text: str
    age: InfermedicaAge
    sex: str | None = None


class InfermedicaQuestionChoice(BaseModel):
    id: str
    label: str


class InfermedicaQuestionItem(BaseModel):
    id: str
    name: str
    choices: list[InfermedicaQuestionChoice]


class InfermedicaQuestion(BaseModel):
    type: str
    text: str
    extras: dict[str, Any] = Field(default_factory=dict)
    items: list[InfermedicaQuestionItem] = Field(default_factory=list)


class InfermedicaCondition(BaseModel):
    id: str
    name: str
    common_name: str
    probability: float


class InfermedicaDiagnosisResponse(BaseModel):
    question: InfermedicaQuestion | None = None
    conditions: list[InfermedicaCondition] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)
    has_emergency_evidence: bool
    interview_token: str


class InfermedicaParseMention(BaseModel):
    id: str
    name: str
    common_name: str
    orth: str
    type: str
    choice_id: str


class InfermedicaParseResponse(BaseModel):
    mentions: list[InfermedicaParseMention] = Field(default_factory=list)
    obvious: bool
