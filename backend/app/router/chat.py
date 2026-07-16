from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agents.graph import graph

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    routed_to: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = graph.invoke({"messages": [HumanMessage(content=request.message)]})
    return ChatResponse(reply=result["messages"][-1].content, routed_to=result.get("next", "respond"))
