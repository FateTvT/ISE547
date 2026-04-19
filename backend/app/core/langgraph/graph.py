from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
import logging
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import settings
from app.core.langgraph.prompts import (
    FIRST_STAGE_NO_EVIDENCE_SYSTEM_PROMPT,
    build_first_stage_no_evidence_user_prompt,
)
from app.infermedica_schemas import InfermedicaAge, InfermedicaParseRequest
from app.service.diagnosis_kb_service import DiagnosisKnowledgeBaseService

logger = logging.getLogger("uvicorn.error")


class GraphState(TypedDict, total=False):
    """Graph state for first-stage interview flow."""

    messages: Annotated[list[BaseMessage], add_messages]
    age: int
    sex: str
    accumulated_user_text: str
    parse_mentions: list[dict[str, str]]
    has_parse_evidence: bool


class StreamEvent(TypedDict):
    """Unified stream event returned by graph streaming."""

    event: str
    payload: str | dict[str, Any]


class SimpleLangGraphAgent:
    """Simple LangGraph agent using OpenRouter and SQLite."""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.DEFAULT_CHAT_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=settings.CHAT_TEMPERATURE,
            streaming=True,
        )
        self._graph: CompiledStateGraph | None = None
        self._checkpointer: AsyncSqliteSaver | None = None
        self._checkpointer_context: AbstractAsyncContextManager[Any] | None = None
        self._diagnosis_kb_service = DiagnosisKnowledgeBaseService()

    @staticmethod
    def _normalize_message_content(content: Any) -> str:
        """Normalize LangChain message content into plain text."""

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _resolve_parse_sex(sex: str | None) -> str | None:
        """Normalize user sex for Infermedica parse payload."""

        normalized = (sex or "undefine").strip().lower()
        if normalized in {"male", "female"}:
            return normalized
        return None

    @staticmethod
    def _build_accumulated_user_text(messages: list[BaseMessage]) -> str:
        """Merge all user messages into one plain text buffer."""

        user_texts = [
            message.content.strip()
            for message in messages
            if isinstance(message, HumanMessage)
            and isinstance(message.content, str)
            and message.content.strip()
        ]
        return "\n".join(user_texts)

    async def _parse_first_stage(self, state: GraphState) -> dict[str, Any]:
        """Parse cumulative user text and extract symptom evidence."""

        messages = state.get("messages", [])
        accumulated_user_text = self._build_accumulated_user_text(messages)
        parse_mentions: list[dict[str, str]] = []
        has_parse_evidence = False

        if accumulated_user_text:
            logger.info(
                "parse_first_stage start: text_len=%s age=%s sex=%s",
                len(accumulated_user_text),
                state.get("age", 30),
                state.get("sex"),
            )
            parse_response = await self._diagnosis_kb_service.parse(
                InfermedicaParseRequest(
                    text=accumulated_user_text,
                    age=InfermedicaAge(value=state.get("age", 30)),
                    sex=self._resolve_parse_sex(state.get("sex")),
                )
            )
            logger.info("Infermedica parse response: %s", parse_response.model_dump())
            parse_mentions = [
                {"id": mention.id, "choice_id": mention.choice_id}
                for mention in parse_response.mentions
            ]
            has_parse_evidence = bool(parse_mentions)
            logger.info(
                "parse_first_stage decision: has_parse_evidence=%s mentions_count=%s",
                has_parse_evidence,
                len(parse_mentions),
            )
        else:
            logger.info("parse_first_stage skipped: no accumulated user text.")

        return {
            "accumulated_user_text": accumulated_user_text,
            "parse_mentions": parse_mentions,
            "has_parse_evidence": has_parse_evidence,
        }

    async def _first_stage_need_more(
        self, state: GraphState
    ) -> dict[str, list[AIMessage]]:
        """Use LLM follow-up when parse evidence is unavailable."""

        fallback_response = AIMessage(
            content=(
                "I could not extract enough symptom evidence yet. "
                "Please describe your main symptom, when it started, how severe it is, "
                "and what makes it better or worse."
            )
        )
        accumulated_user_text = state.get("accumulated_user_text", "")
        parse_mentions = state.get("parse_mentions", [])
        llm_input = [
            SystemMessage(content=FIRST_STAGE_NO_EVIDENCE_SYSTEM_PROMPT),
            HumanMessage(
                content=build_first_stage_no_evidence_user_prompt(
                    accumulated_user_text=accumulated_user_text,
                    age=state.get("age", 30),
                    sex=state.get("sex", "undefine"),
                    parse_mentions_count=len(parse_mentions),
                )
            ),
        ]
        try:
            llm_response = await self._llm.ainvoke(llm_input)
        except Exception:
            logger.exception("first_stage_need_more LLM invocation failed.")
            return {"messages": [fallback_response]}

        response_text = self._normalize_message_content(llm_response.content).strip()
        if not response_text:
            return {"messages": [fallback_response]}
        return {"messages": [AIMessage(content=response_text)]}

    def _first_stage_done(self, state: GraphState) -> dict[str, list[AIMessage]]:
        """Send a stage-complete message when evidence is ready."""

        mentions_count = len(state.get("parse_mentions", []))
        response = AIMessage(
            content=(
                "Thank you. I have enough structured symptom evidence to proceed "
                f"to the next diagnosis step. Parsed evidence count: {mentions_count}."
            )
        )
        return {"messages": [response]}

    @staticmethod
    def _route_after_parse(state: GraphState) -> str:
        """Route to follow-up question or finish first stage."""

        if state.get("has_parse_evidence"):
            return "first_stage_done"
        return "first_stage_need_more"

    def _resolve_sqlite_conn_string(self) -> str:
        """Resolve SQLite checkpointer path from shared DATABASE_URL."""

        database_url = settings.DATABASE_URL.strip()
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            return ":memory:"

        if database_url.startswith("sqlite+aiosqlite:///"):
            sqlite_path = database_url.removeprefix("sqlite+aiosqlite:///")
        elif database_url.startswith("sqlite:///"):
            sqlite_path = database_url.removeprefix("sqlite:///")
        else:
            raise ValueError(
                "DATABASE_URL must be a sqlite URL when using AsyncSqliteSaver, "
                f"got: {database_url}"
            )

        sqlite_path = sqlite_path.split("?", maxsplit=1)[0]
        return sqlite_path if sqlite_path else ":memory:"

    async def _get_sqlite_checkpointer(self) -> AsyncSqliteSaver:
        """Get a reusable SQLite checkpointer for async graph execution."""

        if self._checkpointer is None:
            context_manager = AsyncSqliteSaver.from_conn_string(
                self._resolve_sqlite_conn_string()
            )
            checkpointer = await context_manager.__aenter__()
            await checkpointer.setup()
            self._checkpointer = checkpointer
            self._checkpointer_context = context_manager
        return self._checkpointer

    async def create_graph(self) -> CompiledStateGraph:
        """Create the graph and attach SQLite checkpointer."""

        graph_builder = StateGraph(GraphState)
        graph_builder.add_node("parse_first_stage", self._parse_first_stage)
        graph_builder.add_node("first_stage_need_more", self._first_stage_need_more)
        graph_builder.add_node("first_stage_done", self._first_stage_done)
        graph_builder.add_edge(START, "parse_first_stage")
        graph_builder.add_conditional_edges(
            "parse_first_stage",
            self._route_after_parse,
            {
                "first_stage_need_more": "first_stage_need_more",
                "first_stage_done": "first_stage_done",
            },
        )
        graph_builder.add_edge("first_stage_need_more", END)
        graph_builder.add_edge("first_stage_done", END)

        checkpointer = await self._get_sqlite_checkpointer()
        return graph_builder.compile(
            checkpointer=checkpointer, name="simple-langgraph-agent"
        )

    async def _get_graph(self) -> CompiledStateGraph:
        """Create graph lazily on first request."""

        if self._graph is None:
            self._graph = await self.create_graph()
        return self._graph

    async def get_response(
        self,
        user_message: str,
        session_id: str,
        age: int = 30,
        sex: str = "undefine",
    ) -> str:
        """Get one complete LLM response."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        input_state = {
            "messages": [
                SystemMessage(content=settings.SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
            "age": age,
            "sex": sex,
        }
        result = await graph.ainvoke(input_state, config=config)
        messages = result.get("messages", [])
        if not messages:
            return ""
        return str(messages[-1].content)

    async def stream_response(
        self,
        user_message: str,
        session_id: str,
        resume: str | None = None,
        age: int = 30,
        sex: str = "undefine",
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream LLM chunks and interrupt payloads."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        graph_input: dict[str, Any] | Command
        if resume is not None:
            graph_input = Command(resume=resume)
        else:
            graph_input = {
                "messages": [
                    SystemMessage(content=settings.SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ],
                "age": age,
                "sex": sex,
            }

        chunk_emitted = False
        async for chunk in graph.astream(
            graph_input,
            config=config,
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            if not isinstance(chunk, dict):
                continue

            chunk_type = chunk.get("type")
            if chunk_type == "messages":
                data = chunk.get("data")
                if not isinstance(data, tuple) or not data:
                    continue
                message_chunk = data[0]
                if not isinstance(message_chunk, AIMessageChunk):
                    continue
                if isinstance(message_chunk.content, str) and message_chunk.content:
                    chunk_emitted = True
                    yield {
                        "event": "message",
                        "payload": message_chunk.content,
                    }
                continue

            if chunk_type != "updates":
                continue
            updates = chunk.get("data")
            if not isinstance(updates, dict):
                continue

            if not chunk_emitted:
                for node_update in updates.values():
                    if not isinstance(node_update, dict):
                        continue
                    node_messages = node_update.get("messages")
                    if not isinstance(node_messages, list):
                        continue
                    for node_message in node_messages:
                        if not isinstance(node_message, AIMessage):
                            continue
                        response_text = self._normalize_message_content(
                            node_message.content
                        ).strip()
                        if not response_text:
                            continue
                        yield {"event": "message", "payload": response_text}

            interrupts = updates.get("__interrupt__")
            if not interrupts:
                continue

            first_interrupt = interrupts[0]
            interrupt_payload = getattr(first_interrupt, "value", None)
            if isinstance(interrupt_payload, dict):
                yield {"event": "interrupt", "payload": interrupt_payload}
            elif interrupt_payload is not None:
                yield {
                    "event": "interrupt",
                    "payload": {
                        "question": str(interrupt_payload),
                        "question_choices": [
                            {
                                "choice_id": "free-text",
                                "choice": str(interrupt_payload),
                                "selected": False,
                            }
                        ],
                    },
                }

    async def get_history(self, session_id: str) -> list[BaseMessage]:
        """Get persisted message history by thread ID."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config=config)
        values = getattr(snapshot, "values", {}) or {}
        messages = values.get("messages", [])
        if not isinstance(messages, list):
            return []
        return [message for message in messages if isinstance(message, BaseMessage)]

    async def close(self) -> None:
        """Close SQLite checkpointer resources if they exist."""

        if self._checkpointer_context is not None:
            await self._checkpointer_context.__aexit__(None, None, None)
            self._checkpointer_context = None
            self._checkpointer = None


langgraph_agent = SimpleLangGraphAgent()
