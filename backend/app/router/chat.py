import asyncio
from typing import Literal, Optional

from fastapi import APIRouter
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel

from app.agents.main_agent.main import graph
from app.core.dependencies import CurrentUser
from app.core.logging import get_logger, log_duration
from app.db.session import SessionDep
from app.services import connections as connection_service

router = APIRouter()
logger = get_logger(__name__)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    routed_to: str
    sql: Optional[str] = None
    history: list[ChatMessage]


def _to_lc_messages(history: list[ChatMessage]) -> list[AnyMessage]:
    return [
        HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
        for m in history
    ]


def _to_chat_messages(lc_messages: list[AnyMessage]) -> list[ChatMessage]:
    return [
        ChatMessage(role="user" if isinstance(m, HumanMessage) else "assistant", content=m.content)
        for m in lc_messages
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: CurrentUser, session: SessionDep) -> ChatResponse:
    logger.info("user %s: %s", user.id, request.message)

    # Resolved here, not inside the SQL agent: the agent graph is synchronous and can neither await
    # the annotations read nor rebuild a connection. Stays None when the user has nothing active —
    # plenty of questions never reach the SQL agent, and those must still work without a connection.
    db_context = await connection_service.get_active_db_context(session, user)

    with log_duration("Total query completion"):
        # the graph is sync and spends most of its time in blocking LLM/driver calls, so it runs on
        # a worker thread rather than stalling the event loop for the whole turn
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "chat_history": _to_lc_messages(request.history),
                "db_context": db_context,
                "question": request.message,
                "refined_query": "",
                "next": "",
                "agent_output": None,
                "agent_sql": None,
                "attempts": 0,
                "final_answer": None,
                "final_sql": None,
            },
        )

    routed_to = result.get("next") or "respond"
    logger.info("routed_to=%s", routed_to)
    return ChatResponse(
        reply=result["final_answer"],
        routed_to=routed_to,
        sql=result.get("final_sql"),
        history=_to_chat_messages(result["chat_history"]),
    )
