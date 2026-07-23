from typing import Optional, TypedDict

from app.agents.sql_agent.db import Connection


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
    rows: Optional[list[dict]]
    error: Optional[str]
    blocked_reason: Optional[str]
    fix_attempts: int

    result: Optional[str]
