"""Wires the General agent's graph: rag_agent, analytics_agent, websearch_agent, and the shared
visualizer as specialists under one supervisor, built from the shared scaffold in
app.agents.shared.supervisor.

Deliberately never receives a db_context or any other database-shaped state: that's what makes the
privacy boundary between this agent and the Database agent structural rather than a prompting
convention — see app/router/chat.py, which never resolves a DB connection for a "general" chat.
"""

from app.agents.general_agent.prompts import RESPOND_PROMPT, SYSTEM_PROMPT
from app.agents.general_agent.rag_agent.agent import rag_agent_node
from app.agents.general_agent.state import GeneralAgentState
from app.agents.general_agent.websearch.agent import websearch_agent_node
from app.agents.shared.analytics_ops.agent import make_analytics_agent_node
from app.agents.shared.supervisor import build_agent_graph
from app.agents.shared.visualizer.agent import visualizer_node

NO_CSV = "I don't have a CSV to analyze yet — upload one to this chat and ask again."

analytics_agent_node = make_analytics_agent_node(
    get_data=lambda state: state.get("csv_context"),
    no_data_message=NO_CSV,
    llm_key="csv_agent",
    # confirmed live: this model (qwen3.8-27b) produces malformed/runaway tool calls against the
    # AnalyticsPlan schema under the default tool-calling structured output — json_mode doesn't
    json_mode=True,
)

graph = build_agent_graph(
    state_type=GeneralAgentState,
    agent_name="main_agent",
    system_prompt=SYSTEM_PROMPT,
    respond_prompt=RESPOND_PROMPT,
    specialists={
        "rag_agent": rag_agent_node,
        "analytics_agent": analytics_agent_node,
        "websearch_agent": websearch_agent_node,
        "visualizer": visualizer_node,
    },
)
