from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse

from app.api.deps.auth import get_verified_session
from app.schemas import AIChatRequest
from app.service.chat_service import stream_langgraph_chat, stream_mock_chat

router = APIRouter()


@router.get("/mock", response_class=EventSourceResponse)
async def mock_sse_stream():
    async for event in stream_mock_chat():
        yield event


@router.post("/stream", response_class=EventSourceResponse)
async def stream_chat(
    request: AIChatRequest,
    _verified_user=Depends(get_verified_session),
):
    async for event in stream_langgraph_chat(
        message=request.message, session_id=request.session_id
    ):
        yield event
