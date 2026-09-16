"""Wires the Database agent's graph: sql_agent, analytics_agent, and visualizer as specialists under
one supervisor, built from the shared scaffold in app.agents.shared.supervisor.
"""

from typing import Optional

from app.agents.database_agent.prompts import RESPOND_PROMPT, SYSTEM_PROMPT
from app.agents.database_agent.sql_agent.agents import sql_agent_node
from app.agents.database_agent.state import DatabaseAgentState
from app.agents.shared.analytics_ops.agent import make_analytics_agent_node
from app.agents.shared.supervisor import build_agent_graph
from app.agents.shared.tabular import QueryResult
from app.agents.shared.visualizer.agent import visualizer_node

NO_DATA = (
    "I don't have any query results to analyze yet — nothing has been fetched in this conversation. "
    "Ask for the data you want first and I can run the numbers on it."
)


def _rows(state: dict) -> Optional[QueryResult]:
    """This turn's result if sql_agent already ran once (the supervisor's retry loop handing off
    after a first hop), otherwise the last turn's — same "already fetched" rule visualizer follows.
    """
    if state.get("result_rows") is not None:
        return QueryResult(
            columns=state.get("result_columns") or [],
            rows=state["result_rows"],
            truncated=bool(state.get("result_truncated")),
        )
    return state.get("prior_result")


analytics_agent_node = make_analytics_agent_node(
    get_data=_rows,
    no_data_message=NO_DATA,
    llm_key="analytics_agent",
)

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
