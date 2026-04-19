import asyncio
import json
from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage

from app.core.langgraph.graph import langgraph_agent
from app.schemas import AIChatStreamEventType, QuestionCard, QuestionChoice

MOCK_RESPONSE_CHUNKS = [
    "根据",
    "您提供的",
    "症状描述",
    "（偏头痛、",
    "恶心、",
    "畏光），",
    "系统经过",
    "医学知识库",
    "比对，",
    "为您生成以下",
    "初步分析报告：\n\n",
    "### 1. 可能的诊断结果\n",
    "* **血管性偏头痛** (85% 相关性)\n",
    "* **紧张性头痛** (10% 相关性)\n",
    "* **丛集性头痛** (5% 相关性)\n\n",
    "### 2. 建议采取的措施\n",
    "* **环境调节**：请立即移步至安静、",
    "避光的房间休息。\n",
    "* **体温监测**：记录当前的体温是否伴随发热。\n",
    "* **补充水分**：建议饮用少量的温开水。\n\n",
    "### 3. 需警惕的症状 (Red Flags)\n",
    "如果出现以下情况，请立刻拨打急救电话或前往急诊：\n",
    "* 伴随剧烈的呕吐或言语不清；\n",
    "* 视力突然模糊且无法恢复；\n",
    "* 肢体出现麻木感。\n\n",
    "--- \n",
    "> **免责声明**：本结果基于算法逻辑生成，仅供参考，不作为临床诊断依据。请及时咨询专业医师。",
]


async def stream_mock_chat() -> AsyncIterator[dict[str, str]]:
    """Stream mock chunks for frontend debugging."""

    for index, message in enumerate(MOCK_RESPONSE_CHUNKS, start=1):
        await asyncio.sleep(0.2)
        if index == 1:
            interrupt_payload = QuestionCard(
                question="请先确认是否存在药物过敏史？",
                question_choices=[
                    QuestionChoice(
                        choice_id="allergy-none",
                        choice="没有已知药物过敏史",
                        selected=False,
                    ),
                    QuestionChoice(
                        choice_id="allergy-unknown",
                        choice="不确定，之前没有系统记录",
                        selected=False,
                    ),
                ],
            )
            yield {
                "event": AIChatStreamEventType.INTERRUPT.value,
                "id": "interrupt-1",
                "data": json.dumps(interrupt_payload.model_dump(), ensure_ascii=False),
            }

        payload = {
            "index": index,
            "message": message,
        }
        yield {
            "event": AIChatStreamEventType.MESSAGE.value,
            "id": str(index),
            "data": json.dumps(payload, ensure_ascii=False),
        }


async def stream_langgraph_chat(
    message: str, session_id: str
) -> AsyncIterator[dict[str, str]]:
    """Stream LangGraph/OpenRouter response as SSE payloads."""

    index = 0
    try:
        async for token in langgraph_agent.stream_response(
            user_message=message, session_id=session_id
        ):
            if not token:
                continue
            index += 1
            payload = {"index": index, "message": token}
            yield {
                "event": AIChatStreamEventType.MESSAGE.value,
                "id": str(index),
                "data": json.dumps(payload, ensure_ascii=False),
            }
        interrupt_payload = QuestionCard(
            question="请确认你现在最需要的帮助方向。",
            question_choices=[
                QuestionChoice(
                    choice_id="relief-first",
                    choice="我需要先快速缓解当前症状",
                    selected=False,
                ),
                QuestionChoice(
                    choice_id="diagnosis-first",
                    choice="我想先明确可能的诊断方向",
                    selected=False,
                ),
            ],
        )
        yield {
            "event": AIChatStreamEventType.INTERRUPT.value,
            "id": "interrupt-1",
            "data": json.dumps(interrupt_payload.model_dump(), ensure_ascii=False),
        }
    except Exception:
        payload = {"message": "AI response stream failed. Please retry later."}
        yield {
            "event": AIChatStreamEventType.ERROR.value,
            "id": "error",
            "data": json.dumps(payload, ensure_ascii=False),
        }


def _resolve_message_role(message: BaseMessage) -> str:
    """Map LangChain message type to API response role."""

    if message.type == "human":
        return "user"
    if message.type == "ai":
        return "assistant"
    return message.type


async def get_langgraph_session_history(session_id: str) -> list[dict[str, str]]:
    """Get history for one session/thread from LangGraph checkpoint."""

    messages = await langgraph_agent.get_history(session_id=session_id)
    history: list[dict[str, str]] = []
    for message in messages:
        content = (
            message.content
            if isinstance(message.content, str)
            else str(message.content)
        )
        role = _resolve_message_role(message)
        if role == "system":
            continue
        history.append({"role": role, "content": content})
    return history
