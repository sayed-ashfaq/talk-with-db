import asyncio
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agents.main_agent.main import graph
from app.core.dependencies import CurrentUser
from app.core.logging import get_logger, log_duration
from app.db.models import Message
from app.db.session import SessionDep
from app.services import chats as chat_service
from app.services import connections as connection_service

router = APIRouter()
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    # omit to start a new conversation — the response carries the id to use from then on
    chat_id: Optional[uuid.UUID] = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sql: Optional[str] = None
    routed_to: Optional[str] = None
    created_at: datetime

    @classmethod
    def of(cls, message: Message) -> "MessageResponse":
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            sql=message.sql,
            routed_to=message.routed_to,
            created_at=message.created_at,
        )


class QueryData(BaseModel):
    """The rows behind an answer, when the turn ran a query.

    Live-only: not persisted with the message, so reopening a conversation replays the prose but
    not the table. Charts are what make these worth keeping around, so persistence lands with them.
    """

    columns: list[str]
    rows: list[dict]
    row_count: int
    # the result hit the row cap and there is likely more behind it — the client should say so
    # rather than presenting a capped result as complete
    truncated: bool


class ChatResponse(BaseModel):
    chat_id: uuid.UUID
    # echoed so a client that just started a conversation can name it in the sidebar without
    # re-fetching the list
    title: str
    reply: str
    routed_to: str
    sql: Optional[str] = None
    data: Optional[QueryData] = None
    message: MessageResponse


def _query_data(result: dict) -> Optional[QueryData]:
    """None unless a query actually ran this turn — a greeting, a web lookup or a blocked write all
    leave the state's row fields untouched."""
    rows = result.get("result_rows")
    if rows is None:
        return None
    return QueryData(
        columns=result.get("result_columns") or [],
        rows=rows,
        row_count=len(rows),
        truncated=bool(result.get("result_truncated")),
    )


def _to_lc_messages(history: list[Message]) -> list[AnyMessage]:
    return [
        HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
        for m in history
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: CurrentUser, session: SessionDep) -> ChatResponse:
    logger.info("user %s: %s", user.id, request.message)

    # Resolved here, not inside the SQL agent: the agent graph is synchronous and can neither await
    # the annotations read nor rebuild a connection. Stays None when the user has nothing active —
    # plenty of questions never reach the SQL agent, and those must still work without a connection.
    db_context = await connection_service.get_active_db_context(session, user)

    if request.chat_id is None:
        chat_row = await chat_service.create_chat(
            session,
            user.id,
            title=chat_service.derive_title(request.message),
            connection_id=user.active_connection_id,
        )
        history: list[Message] = []
    else:
        # ownership checked here, before any LLM work — posting into someone else's chat must fail
        # fast rather than after 30 seconds of inference
        chat_row = await chat_service.get_owned_chat(session, user.id, request.chat_id)
        history = await chat_service.load_history(session, chat_row.id)

    with log_duration("Total query completion"):
        # the graph is sync and spends most of its time in blocking LLM/driver calls, so it runs on
        # a worker thread rather than stalling the event loop for the whole turn
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "chat_history": _to_lc_messages(history),
                "db_context": db_context,
                "question": request.message,
                "refined_query": "",
                "next": "",
                "agent_output": None,
                "agent_sql": None,
                "attempts": 0,
                "result_rows": None,
                "result_columns": None,
                "result_truncated": False,
                "final_answer": None,
                "final_sql": None,
            },
        )

    routed_to = result.get("next") or "respond"
    logger.info("routed_to=%s", routed_to)

    # committed only now: a failure above leaves no half-written turn, and an abandoned new chat
    # leaves no empty row
    _, assistant = await chat_service.append_turn(
        session,
        chat_row,
        question=request.message,
        answer=result["final_answer"],
        sql=result.get("final_sql"),
        routed_to=routed_to,
    )

    return ChatResponse(
        chat_id=chat_row.id,
        title=chat_row.title,
        reply=assistant.content,
        routed_to=routed_to,
        sql=assistant.sql,
        data=_query_data(result),
        message=MessageResponse.of(assistant),
    )
