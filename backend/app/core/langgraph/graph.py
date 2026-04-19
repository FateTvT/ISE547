from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
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
from langgraph.types import Command, interrupt

from app.core.config import settings
from app.schemas import QuestionCard, QuestionChoice


class GraphState(TypedDict):
    """Graph state with message history."""

    messages: Annotated[list[BaseMessage], add_messages]


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

    async def _chat(self, state: GraphState) -> dict[str, list[AIMessage]]:
        """Call LLM with current conversation state."""

        response = await self._llm.ainvoke(state["messages"])
        return {"messages": [response]}

    def _ask_human(self, _state: GraphState) -> dict[str, list[BaseMessage]]:
        """Pause graph and expose a question card via interrupt."""

        question_card = QuestionCard(
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
        human_answer = interrupt(question_card.model_dump())
        if human_answer is None:
            return {"messages": []}
        return {"messages": [HumanMessage(content=str(human_answer))]}

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
        graph_builder.add_node("chat", self._chat)
        graph_builder.add_node("ask_human", self._ask_human)
        graph_builder.add_node("chat_after_resume", self._chat)
        graph_builder.add_edge(START, "chat")
        graph_builder.add_edge("chat", "ask_human")
        graph_builder.add_edge("ask_human", "chat_after_resume")
        graph_builder.add_edge("chat_after_resume", END)

        checkpointer = await self._get_sqlite_checkpointer()
        return graph_builder.compile(
            checkpointer=checkpointer, name="simple-langgraph-agent"
        )

    async def _get_graph(self) -> CompiledStateGraph:
        """Create graph lazily on first request."""

        if self._graph is None:
            self._graph = await self.create_graph()
        return self._graph

    async def get_response(self, user_message: str, session_id: str) -> str:
        """Get one complete LLM response."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        input_state = {
            "messages": [
                SystemMessage(content=settings.SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        }
        result = await graph.ainvoke(input_state, config=config)
        messages = result.get("messages", [])
        if not messages:
            return ""
        return str(messages[-1].content)

    async def stream_response(
        self, user_message: str, session_id: str, resume: str | None = None
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
                ]
            }

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
