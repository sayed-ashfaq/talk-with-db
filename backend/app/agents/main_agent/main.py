from typing import Literal

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel

from app.agents.knowledge_agent.agent import knowledge_agent_node
from app.agents.main_agent.state import AgentState
from app.agents.python_agent.agent import python_agent_node
from app.agents.sql_agent.agent import sql_agent_node
from app.core.llm import get_llm
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


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("sql_agent", sql_agent_node)
    graph.add_node("knowledge_agent", knowledge_agent_node)
    graph.add_node("python_agent", python_agent_node)
    graph.add_node("responder", responder_node)

    graph.add_edge(START, "supervisor")
    graph.add_edge("sql_agent", END)
    graph.add_edge("knowledge_agent", END)
    graph.add_edge("python_agent", END)
    graph.add_edge("responder", END)

    return graph.compile()


graph = build_graph()
