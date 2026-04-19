import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse
from sqlmodel import Session, select

from app.api.deps.auth import get_verified_session
from app.core.db import get_session
from app.models.session import Session as ChatSession
from app.schemas import (
    AIChatRequest,
    AIChatStreamEventType,
    SessionDetailResponse,
    SessionResponse,
    UserResponse,
)
from app.service.chat_service import (
    get_langgraph_session_history,
    get_langgraph_session_user_choices,
    stream_langgraph_chat,
    stream_mock_chat,
)

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.get("/mock", response_class=EventSourceResponse)
async def mock_sse_stream():
    async for event in stream_mock_chat():
        yield event


@router.post("/stream", response_class=EventSourceResponse)
async def stream_chat(
    request: AIChatRequest,
    verified_user: UserResponse = Depends(get_verified_session),
    db: Session = Depends(get_session),
):
    resolved_session_id = request.session_id or str(uuid4())
    logger.info(
        "ai-chat stream request: session_id=%s resume=%s age=%s sex=%s message_len=%s",
        resolved_session_id,
        bool(request.resume),
        request.age,
        request.sex,
        len((request.message or "").strip()),
    )

    existing_session = db.get(ChatSession, resolved_session_id)
    if existing_session is None:
        if request.resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found for resume",
            )
        db.add(
            ChatSession(
                id=resolved_session_id,
                user_id=verified_user.id,
                name=(request.message or "").strip()[:50],
                username=verified_user.username,
            )
        )
        db.commit()
    elif existing_session.user_id != verified_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to current user",
        )

    streamed_any_event = False
    streamed_event_count = 0
    try:
        async for event in stream_langgraph_chat(
            message=request.message or "",
            session_id=resolved_session_id,
            resume=request.resume,
            age=request.age,
            sex=request.sex,
        ):
            streamed_any_event = True
            streamed_event_count += 1
            yield event
    except Exception as exc:
        if not streamed_any_event:
            logger.exception("AI chat stream failed before first event.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc) or "AI stream initialization failed",
            ) from exc

        logger.exception("AI chat stream failed during SSE response.")
        payload = {"message": str(exc) or "AI response stream failed."}
        yield {
            "event": AIChatStreamEventType.ERROR.value,
            "id": "error",
            "data": json.dumps(payload, ensure_ascii=False),
        }
    else:
        logger.info(
            "ai-chat stream finished: session_id=%s events=%s",
            resolved_session_id,
            streamed_event_count,
        )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    verified_user: UserResponse = Depends(get_verified_session),
    db: Session = Depends(get_session),
) -> list[SessionResponse]:
    rows = db.exec(
        select(ChatSession)
        .where(ChatSession.user_id == verified_user.id)
        .order_by(ChatSession.created_at.desc())
    ).all()
    return [SessionResponse(id=row.id, name=row.name) for row in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    verified_user: UserResponse = Depends(get_verified_session),
    db: Session = Depends(get_session),
) -> SessionDetailResponse:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if row.user_id != verified_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to current user",
        )

    history = await get_langgraph_session_history(session_id=session_id)
    user_choices = await get_langgraph_session_user_choices(session_id=session_id)
    return SessionDetailResponse(
        id=row.id,
        name=row.name,
        messages=history,
        user_choices=user_choices,
    )
