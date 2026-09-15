"""Top-level state for the Database agent — sql_agent, analytics_agent, and visualizer all read and
write this. Carried over unchanged from the pre-split main_agent.state.AgentState: only the module
moved, the shape didn't, so app.services.results (reads these fields by key off a plain dict) needed
no changes at all.
"""

from typing import Optional

from app.agents.shared.state import BaseAgentState
from app.agents.database_agent.sql_agent.db import DbContext
from app.agents.shared.tabular import QueryResult
from app.agents.shared.visualizer.charts import ChartSpec
from app.agents.shared.visualizer.profile import ResultProfile


class DatabaseAgentState(BaseAgentState):
    # the requesting user's database, resolved by the router before the graph runs — agent nodes are
    # synchronous and can neither await the metadata store nor reach into the connection registry.
    # None when the user has no active connection.
    db_context: Optional[DbContext]

    # what the last query in this conversation returned, read back from the stored turn by the
    # router — same reason db_context is resolved there: the graph is synchronous and can't await a
    # database of our own. This is what lets "show that as a pie chart" answer from the rows the
    # user already has, instead of asking their database the same question twice.
    prior_result: Optional[QueryResult]

    agent_sql: Optional[str]

    # The rows behind the answer, carried alongside agent_output rather than through it.
    #
    # Every specialist overwrites agent_output and finalize hands whichever one ran last to the
    # user, so anything that has to survive a second hop cannot live in that field — route
    # sql_agent -> visualizer through it and the SQL answer is gone by the time the user sees a
    # chart. These stay put until another query replaces them.
    #
    # Deliberately never shown to the supervisor: its decision context is built from prose, and a
    # few thousand rows of JSON in there would cost more than the whole rest of the turn.
    result_rows: Optional[list[dict]]
    result_columns: Optional[list[str]]
    result_truncated: bool

    # how to draw those rows, and what shape they are. Both None when the result isn't worth a
    # chart, which is an ordinary outcome — most questions are answered by a sentence.
    chart_spec: Optional[ChartSpec]
    chart_profile: Optional[ResultProfile]

    final_sql: Optional[str]
