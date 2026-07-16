from typing import Literal

from fastapi import APIRouter
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel

from app.agents.main_agent.main import graph
from app.core.logging import get_logger, log_duration

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
def chat(request: ChatRequest) -> ChatResponse:
    logger.info("received message: %s", request.message)

    with log_duration("Total query completion"):
        result = graph.invoke(
            {
                "chat_history": _to_lc_messages(request.history),
                "question": request.message,
                "refined_query": "",
                "next": "",
                "agent_output": None,
                "attempts": 0,
                "final_answer": None,
            }
        )

    routed_to = result.get("next") or "respond"
    logger.info("routed_to=%s", routed_to)
    return ChatResponse(
        reply=result["final_answer"],
        routed_to=routed_to,
        history=_to_chat_messages(result["chat_history"]),
    )
