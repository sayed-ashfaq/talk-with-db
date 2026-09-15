"""Wires the Database agent's graph: sql_agent, analytics_agent, and visualizer as specialists under
one supervisor, built from the shared scaffold in app.agents.shared.supervisor.
"""

from app.agents.database_agent.analytics_agent.agent import analytics_agent_node
from app.agents.database_agent.prompts import RESPOND_PROMPT, SYSTEM_PROMPT
from app.agents.database_agent.sql_agent.agents import sql_agent_node
from app.agents.database_agent.state import DatabaseAgentState
from app.agents.shared.supervisor import build_agent_graph
from app.agents.shared.visualizer.agent import visualizer_node

graph = build_agent_graph(
    state_type=DatabaseAgentState,
    agent_name="main_agent",
    system_prompt=SYSTEM_PROMPT,
    respond_prompt=RESPOND_PROMPT,
    specialists={
        "sql_agent": sql_agent_node,
        "analytics_agent": analytics_agent_node,
        "visualizer": visualizer_node,
    },
    # agent_sql -> final_sql: the only field that needs an explicit carry-over at finalize time.
    # Everything else a specialist writes (result_rows, chart_spec, ...) is already part of the
    # graph's accumulated state by the time invoke() returns, with no rename needed.
    extra_finalize=lambda state: {"final_sql": state.get("agent_sql")},
)
