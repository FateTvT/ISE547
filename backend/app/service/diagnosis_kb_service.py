"""Infermedica diagnosis knowledge base integration service."""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.infermedica_schemas import (
    InfermedicaDiagnosisRequest,
    InfermedicaDiagnosisResponse,
    InfermedicaParseRequest,
    InfermedicaParseResponse,
)


class DiagnosisKnowledgeBaseService:
    """Call Infermedica diagnosis API with typed payloads."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _post(self, path: str, payload: dict) -> dict:
        """Send a JSON POST to Infermedica and return JSON body."""

        headers = {
            "App-Id": settings.INFERMEDICA_APP_ID,
            "App-Key": settings.INFERMEDICA_APP_KEY,
            "Accept-Language": settings.INFERMEDICA_LANGUAGE,
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(settings.INFERMEDICA_TIMEOUT_SECONDS)
        endpoint = f"{settings.INFERMEDICA_BASE_URL.rstrip('/')}/{path.lstrip('/')}"

        if self._client is not None:
            response = await self._client.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )

        response.raise_for_status()
        return response.json()

    async def diagnose(
        self, request_payload: InfermedicaDiagnosisRequest
    ) -> InfermedicaDiagnosisResponse:
        """Send diagnosis request and parse typed response."""

        payload = await self._post("diagnosis", request_payload.model_dump())
        return InfermedicaDiagnosisResponse.model_validate(payload)

    async def parse(
        self, request_payload: InfermedicaParseRequest
    ) -> InfermedicaParseResponse:
        """Send parse request and parse typed response."""

        payload = await self._post(
            "parse", request_payload.model_dump(exclude_none=True)
        )
        return InfermedicaParseResponse.model_validate(payload)
