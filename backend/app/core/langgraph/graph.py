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
from langgraph.types import Command, interrupt

from app.core.config import settings
from app.core.langgraph.prompts import (
    FINAL_DIAGNOSIS_SUMMARY_SYSTEM_PROMPT,
    FIRST_STAGE_NO_EVIDENCE_SYSTEM_PROMPT,
    build_final_diagnosis_user_prompt,
    build_first_stage_no_evidence_user_prompt,
)
from app.infermedica_schemas import (
    InfermedicaAge,
    InfermedicaDiagnosisRequest,
    InfermedicaParseRequest,
    InfermedicaQuestion,
)
from app.schemas import QuestionCard, QuestionChoice
from app.service.diagnosis_kb_service import DiagnosisKnowledgeBaseService

logger = logging.getLogger("uvicorn.error")
FINAL_RESULT_CHOICE_ID = "__view_final_result__"
EVIDENCE_CHOICE_PREFIX = "evidence"


class GraphState(TypedDict, total=False):
    """Graph state for interview and diagnosis flow."""

    messages: Annotated[list[BaseMessage], add_messages]
    age: int
    sex: str
    accumulated_user_text: str
    parse_mentions: list[dict[str, str]]
    evidence: list[dict[str, str]]
    has_parse_evidence: bool
    diagnosis_payload: dict[str, Any]
    question_card: dict[str, Any]
    has_kb_question: bool
    selected_kb_choice: str
    user_wants_final_result: bool


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
    def _resolve_diagnosis_sex(sex: str | None) -> str:
        """Resolve diagnosis sex with fallback accepted by Infermedica."""

        normalized = SimpleLangGraphAgent._resolve_parse_sex(sex)
        return normalized or "male"

    @staticmethod
    def _build_evidence_choice_token(evidence_id: str, choice_id: str) -> str:
        """Build a stable choice token carrying evidence selection."""

        return f"{EVIDENCE_CHOICE_PREFIX}::{evidence_id}::{choice_id}"

    @staticmethod
    def _parse_evidence_choice_token(choice_token: str) -> tuple[str, str] | None:
        """Parse evidence token and return evidence ID with choice ID."""

        parts = choice_token.split("::")
        if len(parts) != 3 or parts[0] != EVIDENCE_CHOICE_PREFIX:
            return None
        evidence_id = parts[1].strip()
        choice_id = parts[2].strip()
        if not evidence_id or not choice_id:
            return None
        return evidence_id, choice_id

    @staticmethod
    def _extract_choice_id_from_interrupt_answer(answer: Any) -> str | None:
        """Extract a choice ID string from interrupt resume payload."""

        if isinstance(answer, str):
            choice_id = answer.strip()
            return choice_id or None
        if isinstance(answer, dict):
            possible = answer.get("choice_id")
            if isinstance(possible, str) and possible.strip():
                return possible.strip()
        return None

    @staticmethod
    def _build_question_card(question: InfermedicaQuestion) -> dict[str, Any]:
        """Convert Infermedica follow-up question to frontend question card."""

        question_choices: list[QuestionChoice] = []
        has_multi_items = len(question.items) > 1
        for item in question.items:
            item_name = item.name.strip()
            for choice in item.choices:
                label = (
                    f"{item_name}: {choice.label}"
                    if has_multi_items and item_name
                    else choice.label
                )
                question_choices.append(
                    QuestionChoice(
                        choice_id=SimpleLangGraphAgent._build_evidence_choice_token(
                            item.id, choice.id
                        ),
                        choice=label,
                        selected=False,
                    )
                )
        question_choices.append(
            QuestionChoice(
                choice_id=FINAL_RESULT_CHOICE_ID,
                choice="Skip more questions and show final result now.",
                selected=False,
            )
        )
        return QuestionCard(
            question=question.text,
            question_choices=question_choices,
        ).model_dump()

    @staticmethod
    def _update_evidence(
        evidence: list[dict[str, str]], evidence_id: str, choice_id: str
    ) -> list[dict[str, str]]:
        """Upsert one evidence decision and keep other evidence unchanged."""

        next_evidence = [
            item
            for item in evidence
            if item.get("id") != evidence_id or not item.get("id")
        ]
        next_evidence.append({"id": evidence_id, "choice_id": choice_id})
        return next_evidence

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

        evidence = [
            {"id": mention["id"], "choice_id": mention["choice_id"]}
            for mention in parse_mentions
        ]
        return {
            "accumulated_user_text": accumulated_user_text,
            "parse_mentions": parse_mentions,
            "evidence": evidence,
            "has_parse_evidence": has_parse_evidence,
            "user_wants_final_result": False,
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

    async def _diagnosis_kb_step(self, state: GraphState) -> dict[str, Any]:
        """Call diagnosis API and prepare next question or final payload."""

        evidence = state.get("evidence", [])
        if not evidence:
            logger.info("diagnosis_kb_step skipped: no evidence available.")
            return {
                "has_kb_question": False,
                "diagnosis_payload": {},
                "question_card": {},
            }

        diagnosis_response = await self._diagnosis_kb_service.diagnose(
            InfermedicaDiagnosisRequest(
                sex=self._resolve_diagnosis_sex(state.get("sex")),
                age=InfermedicaAge(value=state.get("age", 30)),
                evidence=evidence,
            )
        )
        diagnosis_payload = diagnosis_response.model_dump()
        logger.info("Infermedica diagnosis response: %s", diagnosis_payload)
        if diagnosis_response.question is None:
            return {
                "has_kb_question": False,
                "diagnosis_payload": diagnosis_payload,
                "question_card": {},
            }
        return {
            "has_kb_question": True,
            "diagnosis_payload": diagnosis_payload,
            "question_card": self._build_question_card(diagnosis_response.question),
        }

    def _ask_human_for_kb_choice(self, state: GraphState) -> dict[str, Any]:
        """Interrupt and ask user how to continue diagnosis interview."""

        question_card = state.get("question_card")
        if not isinstance(question_card, dict) or not question_card:
            return {"selected_kb_choice": FINAL_RESULT_CHOICE_ID}
        human_answer = interrupt(question_card)
        selected_choice = self._extract_choice_id_from_interrupt_answer(human_answer)
        return {"selected_kb_choice": selected_choice or FINAL_RESULT_CHOICE_ID}

    def _apply_user_choice_to_evidence(self, state: GraphState) -> dict[str, Any]:
        """Apply selected option to evidence or mark final-result preference."""

        selected_choice = (state.get("selected_kb_choice") or "").strip()
        if selected_choice == FINAL_RESULT_CHOICE_ID or not selected_choice:
            return {"user_wants_final_result": True}

        parsed_choice = self._parse_evidence_choice_token(selected_choice)
        if parsed_choice is None:
            return {"user_wants_final_result": True}

        evidence_id, choice_id = parsed_choice
        next_evidence = self._update_evidence(
            state.get("evidence", []),
            evidence_id=evidence_id,
            choice_id=choice_id,
        )
        return {
            "evidence": next_evidence,
            "user_wants_final_result": False,
        }

    async def _final_diagnosis_summary(
        self, state: GraphState
    ) -> dict[str, list[AIMessage]]:
        """Summarize diagnosis payload into final response via LLM."""

        diagnosis_payload = state.get("diagnosis_payload", {})
        if not isinstance(diagnosis_payload, dict) or not diagnosis_payload:
            response = AIMessage(
                content=(
                    "I do not have enough diagnosis data to produce a final result yet. "
                    "Please provide more symptom details and try again."
                )
            )
            return {"messages": [response]}

        llm_input = [
            SystemMessage(content=FINAL_DIAGNOSIS_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(
                content=build_final_diagnosis_user_prompt(
                    accumulated_user_text=state.get("accumulated_user_text", ""),
                    age=state.get("age", 30),
                    sex=state.get("sex", "undefine"),
                    evidence_count=len(state.get("evidence", [])),
                    diagnosis_payload=diagnosis_payload,
                )
            ),
        ]
        try:
            llm_response = await self._llm.ainvoke(llm_input)
        except Exception:
            logger.exception("final_diagnosis_summary LLM invocation failed.")
            fallback = AIMessage(
                content=(
                    "I have generated diagnosis candidates from the knowledge base, "
                    "but I could not format the final summary right now."
                )
            )
            return {"messages": [fallback]}

        response_text = self._normalize_message_content(llm_response.content).strip()
        if not response_text:
            response_text = (
                "I generated the diagnosis result, but the final summary is empty. "
                "Please try again."
            )
        return {"messages": [AIMessage(content=response_text)]}

    @staticmethod
    def _route_after_parse(state: GraphState) -> str:
        """Route to follow-up or diagnosis knowledge-base stage."""

        if state.get("has_parse_evidence"):
            return "diagnosis_kb_step"
        return "first_stage_need_more"

    @staticmethod
    def _route_after_diagnosis(state: GraphState) -> str:
        """Route from diagnosis response to interrupt or final summary."""

        if state.get("has_kb_question") and not state.get("user_wants_final_result"):
            return "ask_human_for_kb_choice"
        return "final_diagnosis_summary"

    @staticmethod
    def _route_after_apply_choice(state: GraphState) -> str:
        """Route after user selection to continue or finalize."""

        if state.get("user_wants_final_result"):
            return "final_diagnosis_summary"
        return "diagnosis_kb_step"

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
        graph_builder.add_node("diagnosis_kb_step", self._diagnosis_kb_step)
        graph_builder.add_node("ask_human_for_kb_choice", self._ask_human_for_kb_choice)
        graph_builder.add_node(
            "apply_user_choice_to_evidence", self._apply_user_choice_to_evidence
        )
        graph_builder.add_node("final_diagnosis_summary", self._final_diagnosis_summary)
        graph_builder.add_edge(START, "parse_first_stage")
        graph_builder.add_conditional_edges(
            "parse_first_stage",
            self._route_after_parse,
            {
                "first_stage_need_more": "first_stage_need_more",
                "diagnosis_kb_step": "diagnosis_kb_step",
            },
        )
        graph_builder.add_conditional_edges(
            "diagnosis_kb_step",
            self._route_after_diagnosis,
            {
                "ask_human_for_kb_choice": "ask_human_for_kb_choice",
                "final_diagnosis_summary": "final_diagnosis_summary",
            },
        )
        graph_builder.add_edge(
            "ask_human_for_kb_choice",
            "apply_user_choice_to_evidence",
        )
        graph_builder.add_conditional_edges(
            "apply_user_choice_to_evidence",
            self._route_after_apply_choice,
            {
                "diagnosis_kb_step": "diagnosis_kb_step",
                "final_diagnosis_summary": "final_diagnosis_summary",
            },
        )
        graph_builder.add_edge("first_stage_need_more", END)
        graph_builder.add_edge("final_diagnosis_summary", END)

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
