from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agents.main_agent.main import graph
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    routed_to: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    logger.info("received message: %s", request.message)
    result = graph.invoke({"messages": [HumanMessage(content=request.message)]})
    routed_to = result.get("next", "respond")
    logger.info("routed_to=%s", routed_to)
    return ChatResponse(reply=result["messages"][-1].content, routed_to=routed_to)
