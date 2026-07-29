from typing import Optional, TypedDict

from app.agents.sql_agent.db import Connection, QueryResult


class SQLAgentState(TypedDict):
    refined_query: str
    # the specific database to execute against — carried through state rather than looked up, so
    # two users querying at the same time cannot land on each other's connection
    connection: Connection
    db_type: str
    db_name: str
    schema_text: str

    sql_draft: Optional[str]
    cleaned_sql: Optional[str]
    # the rows themselves, kept whole. The synthesizer is shown a slice of this and the caller gets
    # all of it — a chart needs the data behind the summary, not the fifty rows that described it.
    query_result: Optional[QueryResult]
    error: Optional[str]
    blocked_reason: Optional[str]
    fix_attempts: int

    # the prose answer, named apart from query_result so the two are not mistaken for each other
    answer: Optional[str]
