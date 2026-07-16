from typing import Literal

from langchain_core.messages import SystemMessage
from langgraph.types import Command
from pydantic import BaseModel

from app.agents.state import AgentState
from app.llm import get_llm
from app.prompts.main_agent import SYSTEM_PROMPT

ROUTES = Literal["sql_agent", "knowledge_agent", "python_agent", "respond"]


class Route(BaseModel):
    next: ROUTES
    reasoning: str


def supervisor_node(
    state: AgentState,
) -> Command[Literal["sql_agent", "knowledge_agent", "python_agent", "responder"]]:
    router = get_llm("main_agent").with_structured_output(Route)
    decision = router.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])

    goto = "responder" if decision.next == "respond" else decision.next
    return Command(goto=goto, update={"next": decision.next})


def responder_node(state: AgentState) -> dict:
    llm = get_llm("main_agent")
    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [response]}
