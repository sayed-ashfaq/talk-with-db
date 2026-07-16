from langgraph.graph import END, START, StateGraph

from app.agents.knowledge_agent import knowledge_agent_node
from app.agents.main_agent import responder_node, supervisor_node
from app.agents.python_agent import python_agent_node
from app.agents.sql_agent import sql_agent_node
from app.agents.state import AgentState


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
