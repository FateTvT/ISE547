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
GROUP_SINGLE_CHOICE_PREFIX = "group_single"
ITEM_PRESENT_CHOICE_PREFIX = "item_present"


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
    user_choice_history: list[dict[str, Any]]
    user_wants_final_result: bool
    diagnosis_completed: bool
    pending_user_choice: dict[str, Any] | None


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
    def _build_group_single_choice_token(evidence_id: str) -> str:
        """Build a token for group-single top-level selections."""

        return f"{GROUP_SINGLE_CHOICE_PREFIX}::{evidence_id}"

    @staticmethod
    def _build_item_present_choice_token(evidence_id: str) -> str:
        """Build a token for non-group-single top-level symptom selections."""

        return f"{ITEM_PRESENT_CHOICE_PREFIX}::{evidence_id}"

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
    def _parse_group_single_choice_token(choice_token: str) -> str | None:
        """Parse group-single token and return selected evidence ID."""

        parts = choice_token.split("::")
        if len(parts) != 2 or parts[0] != GROUP_SINGLE_CHOICE_PREFIX:
            return None
        evidence_id = parts[1].strip()
        if not evidence_id:
            return None
        return evidence_id

    @staticmethod
    def _parse_item_present_choice_token(choice_token: str) -> str | None:
        """Parse top-level symptom token and return selected evidence ID."""

        parts = choice_token.split("::")
        if len(parts) != 2 or parts[0] != ITEM_PRESENT_CHOICE_PREFIX:
            return None
        evidence_id = parts[1].strip()
        if not evidence_id:
            return None
        return evidence_id

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
    def _append_user_choice_history(
        *,
        state: GraphState,
        selected_choice: str,
        question_card: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Append one user choice and question snapshot to history."""

        history = state.get("user_choice_history", [])
        if not isinstance(history, list):
            history = []
        entry: dict[str, Any] = {"choice_id": selected_choice}
        normalized_question_card = (
            SimpleLangGraphAgent._normalize_question_card_payload(question_card)
        )
        if normalized_question_card is not None:
            entry["question_card"] = normalized_question_card
        return [*history, entry]

    @staticmethod
    def _normalize_question_card_payload(
        question_card: Any,
    ) -> dict[str, Any] | None:
        """Validate and normalize a question card payload."""

        if not isinstance(question_card, dict):
            return None
        try:
            return QuestionCard.model_validate(question_card).model_dump()
        except Exception:
            logger.exception("Invalid question card payload in choice history.")
            return None

    @staticmethod
    def _is_group_single_question(question: InfermedicaQuestion) -> bool:
        """Check whether question should be rendered as top-level choices."""

        return question.type == "group_single" and bool(question.items)

    @staticmethod
    def _resolve_item_choice_id(
        choice_ids: list[str], preferred_choice_id: str, fallback_choice_id: str
    ) -> str:
        """Resolve choice ID with safe fallback."""

        if preferred_choice_id in choice_ids:
            return preferred_choice_id
        if fallback_choice_id in choice_ids:
            return fallback_choice_id
        return choice_ids[0] if choice_ids else fallback_choice_id

    @staticmethod
    def _build_group_single_evidence_updates(
        question: InfermedicaQuestion, selected_evidence_id: str
    ) -> list[dict[str, str]]:
        """Expand one top-level group-single selection into evidence updates."""

        item_ids = {item.id for item in question.items}
        if selected_evidence_id not in item_ids:
            return []

        updates: list[dict[str, str]] = []
        for item in question.items:
            available_choice_ids = [choice.id for choice in item.choices]
            preferred = "present" if item.id == selected_evidence_id else "absent"
            choice_id = SimpleLangGraphAgent._resolve_item_choice_id(
                available_choice_ids,
                preferred_choice_id=preferred,
                fallback_choice_id="unknown",
            )
            updates.append({"id": item.id, "choice_id": choice_id})
        return updates

    @staticmethod
    def _extract_question_from_payload(
        diagnosis_payload: dict[str, Any],
    ) -> InfermedicaQuestion | None:
        """Extract and validate diagnosis question payload."""

        question_data = diagnosis_payload.get("question")
        if not isinstance(question_data, dict):
            return None
        try:
            return InfermedicaQuestion.model_validate(question_data)
        except Exception:
            logger.exception(
                "Invalid diagnosis question payload for follow-up parsing."
            )
            return None

    @staticmethod
    def _build_question_card(question: InfermedicaQuestion) -> dict[str, Any]:
        """Convert Infermedica follow-up question to frontend question card."""

        question_choices: list[QuestionChoice] = []
        if SimpleLangGraphAgent._is_group_single_question(question):
            for item in question.items:
                label = item.name.strip() or item.id
                question_choices.append(
                    QuestionChoice(
                        choice_id=SimpleLangGraphAgent._build_group_single_choice_token(
                            item.id
                        ),
                        choice=label,
                        selected=False,
                    )
                )
        else:
            for item in question.items:
                label = item.name.strip() or item.id
                question_choices.append(
                    QuestionChoice(
                        choice_id=SimpleLangGraphAgent._build_item_present_choice_token(
                            item.id
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
    def _apply_group_single_selection(
        *, selected_evidence_id: str, state: GraphState
    ) -> dict[str, Any]:
        """Apply group-single top-level selection to evidence state."""

        diagnosis_payload = state.get("diagnosis_payload", {})
        if not isinstance(diagnosis_payload, dict):
            return {"user_wants_final_result": True}

        question = SimpleLangGraphAgent._extract_question_from_payload(
            diagnosis_payload
        )
        if question is None:
            return {"user_wants_final_result": True}
        if not SimpleLangGraphAgent._is_group_single_question(question):
            return {"user_wants_final_result": True}

        updates = SimpleLangGraphAgent._build_group_single_evidence_updates(
            question=question,
            selected_evidence_id=selected_evidence_id,
        )
        if not updates:
            return {"user_wants_final_result": True}

        next_evidence = state.get("evidence", [])
        for update in updates:
            next_evidence = SimpleLangGraphAgent._update_evidence(
                next_evidence,
                evidence_id=update["id"],
                choice_id=update["choice_id"],
            )
        return {
            "evidence": next_evidence,
            "user_wants_final_result": False,
        }

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
            "user_choice_history": [],
            "user_wants_final_result": False,
            "diagnosis_completed": False,
            "pending_user_choice": None,
        }

    @staticmethod
    def _mark_pending_user_choice(state: GraphState) -> dict[str, Any]:
        """Mark state as waiting for user choice before interrupt."""

        question_card = SimpleLangGraphAgent._normalize_question_card_payload(
            state.get("question_card")
        )
        return {"pending_user_choice": question_card}

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
            selected_choice = FINAL_RESULT_CHOICE_ID
            return {
                "selected_kb_choice": selected_choice,
                "user_choice_history": self._append_user_choice_history(
                    state=state,
                    selected_choice=selected_choice,
                ),
                "pending_user_choice": None,
            }
        human_answer = interrupt(question_card)
        selected_choice = self._extract_choice_id_from_interrupt_answer(human_answer)
        resolved_choice = selected_choice or FINAL_RESULT_CHOICE_ID
        return {
            "selected_kb_choice": resolved_choice,
            "user_choice_history": self._append_user_choice_history(
                state=state,
                selected_choice=resolved_choice,
                question_card=question_card,
            ),
            "pending_user_choice": None,
        }

    def _apply_user_choice_to_evidence(self, state: GraphState) -> dict[str, Any]:
        """Apply selected option to evidence or mark final-result preference."""

        selected_choice = (state.get("selected_kb_choice") or "").strip()
        if selected_choice == FINAL_RESULT_CHOICE_ID or not selected_choice:
            return {"user_wants_final_result": True}

        selected_group_single_evidence_id = self._parse_group_single_choice_token(
            selected_choice
        )
        if selected_group_single_evidence_id is not None:
            return self._apply_group_single_selection(
                selected_evidence_id=selected_group_single_evidence_id,
                state=state,
            )

        selected_item_present_evidence_id = self._parse_item_present_choice_token(
            selected_choice
        )
        if selected_item_present_evidence_id is not None:
            next_evidence = self._update_evidence(
                state.get("evidence", []),
                evidence_id=selected_item_present_evidence_id,
                choice_id="present",
            )
            return {
                "evidence": next_evidence,
                "user_wants_final_result": False,
            }

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
            return {"messages": [fallback], "diagnosis_completed": True}

        response_text = self._normalize_message_content(llm_response.content).strip()
        if not response_text:
            response_text = (
                "I generated the diagnosis result, but the final summary is empty. "
                "Please try again."
            )
        return {
            "messages": [AIMessage(content=response_text)],
            "diagnosis_completed": True,
        }

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
            return "mark_pending_user_choice"
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
        """Create the diagnosis interview graph.

        Architecture:
        1. Parse all accumulated user text into initial evidence.
        2. If no evidence is found, ask the user for richer symptom details and stop.
        3. If evidence exists, call diagnosis KB and either:
           - ask a follow-up question and loop with user-selected evidence updates, or
           - generate final diagnosis summary and finish.
        """

        graph_builder = StateGraph(GraphState)
        # Stage 1: parse user input and decide whether follow-up is needed.
        graph_builder.add_node("parse_first_stage", self._parse_first_stage)
        graph_builder.add_node("first_stage_need_more", self._first_stage_need_more)
        # Stage 2: diagnosis KB iteration with optional human-in-the-loop selection.
        graph_builder.add_node("diagnosis_kb_step", self._diagnosis_kb_step)
        graph_builder.add_node(
            "mark_pending_user_choice", self._mark_pending_user_choice
        )
        graph_builder.add_node("ask_human_for_kb_choice", self._ask_human_for_kb_choice)
        graph_builder.add_node(
            "apply_user_choice_to_evidence", self._apply_user_choice_to_evidence
        )
        # Stage 3: final LLM summary for diagnosis payload.
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
                "mark_pending_user_choice": "mark_pending_user_choice",
                "final_diagnosis_summary": "final_diagnosis_summary",
            },
        )
        graph_builder.add_edge("mark_pending_user_choice", "ask_human_for_kb_choice")
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
        diagnosis_down_emitted = False
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

            if not diagnosis_down_emitted:
                for node_update in updates.values():
                    if not isinstance(node_update, dict):
                        continue
                    if bool(node_update.get("diagnosis_completed", False)):
                        diagnosis_down_emitted = True
                        yield {
                            "event": "diagnosis_down",
                            "payload": {"diagnosis_completed": True},
                        }
                        break

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

    async def get_user_choice_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get persisted user choice history by thread ID."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config=config)
        values = getattr(snapshot, "values", {}) or {}
        choice_history = values.get("user_choice_history", [])
        if not isinstance(choice_history, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in choice_history:
            if not isinstance(item, dict):
                continue
            choice_id = item.get("choice_id")
            if not isinstance(choice_id, str) or not choice_id.strip():
                continue
            normalized_item: dict[str, Any] = {"choice_id": choice_id.strip()}
            question_card = self._normalize_question_card_payload(
                item.get("question_card")
            )
            if question_card is not None:
                normalized_item["question_card"] = question_card
            normalized.append(normalized_item)
        return normalized

    async def is_diagnosis_completed(self, session_id: str) -> bool:
        """Check whether diagnosis is marked completed in graph state."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config=config)
        values = getattr(snapshot, "values", {}) or {}
        return bool(values.get("diagnosis_completed", False))

    async def get_pending_user_choice(self, session_id: str) -> dict[str, Any] | None:
        """Get pending interrupt payload stored in graph state."""

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config=config)
        values = getattr(snapshot, "values", {}) or {}
        return self._normalize_question_card_payload(values.get("pending_user_choice"))

    async def close(self) -> None:
        """Close SQLite checkpointer resources if they exist."""

        if self._checkpointer_context is not None:
            await self._checkpointer_context.__aexit__(None, None, None)
            self._checkpointer_context = None
            self._checkpointer = None


langgraph_agent = SimpleLangGraphAgent()
