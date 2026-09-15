"""Top-level state for the General agent — rag_agent, csv_agent, websearch_agent, and the shared
visualizer all read and write this.
"""

from typing import Optional
from uuid import UUID

from app.agents.shared.state import BaseAgentState
from app.agents.shared.tabular import QueryResult
from app.agents.shared.visualizer.charts import ChartSpec
from app.agents.shared.visualizer.profile import ResultProfile


class GeneralAgentState(BaseAgentState):
    # resolved by the router before the graph runs, same reason DatabaseAgentState.db_context is:
    # agent nodes are synchronous and can't await the metadata store mid-graph. rag_agent scopes
    # retrieval to this user's library documents plus this chat's own uploads.
    user_id: UUID
    chat_id: Optional[UUID]

    # this chat's most recent CSV upload, read back by the router before the graph runs — same
    # "resolved outside, because the graph can't await" reasoning as prior_result below.
    csv_context: Optional[QueryResult]

    # what the last analytics/csv turn in this conversation produced, so "show that as a bar chart"
    # can answer from rows already in hand instead of re-running anything.
    prior_result: Optional[QueryResult]

    # only ever None here — the General agent has no SQL to report — but the shared visualizer node
    # writes this key unconditionally (it's meaningful on the Database agent side), so it has to
    # exist on this state too or LangGraph rejects the update.
    agent_sql: Optional[str]

    result_rows: Optional[list[dict]]
    result_columns: Optional[list[str]]
    result_truncated: bool

    chart_spec: Optional[ChartSpec]
    chart_profile: Optional[ResultProfile]
