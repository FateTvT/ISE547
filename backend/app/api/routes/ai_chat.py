from fastapi import APIRouter
from fastapi.sse import EventSourceResponse

from app.service.chat_service import stream_mock_chat

router = APIRouter()


@router.get("/mock", response_class=EventSourceResponse)
async def mock_sse_stream():
    async for event in stream_mock_chat():
        yield event
