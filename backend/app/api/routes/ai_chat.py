import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import AIChatRequest

router = APIRouter()


@router.post("/")
async def ai_chat(payload: AIChatRequest) -> StreamingResponse:
    async def event_stream():
        chunks = [
            "This ",
            "is ",
            "a ",
            "mock ",
            "AI ",
            "chat ",
            "response.",
        ]

        for index, chunk in enumerate(chunks):
            yield f"data: {json.dumps({'index': index, 'content': chunk, 'done': False, 'message': payload.message})}\n\n"
            await asyncio.sleep(0.1)

        yield f"data: {json.dumps({'index': len(chunks), 'content': '', 'done': True, 'message': payload.message})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
