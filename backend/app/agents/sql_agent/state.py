from typing import Optional, TypedDict


class SQLAgentState(TypedDict):
    refined_query: str
    db_type: str
    db_name: str
    schema_text: str

    sql_draft: Optional[str]
    cleaned_sql: Optional[str]
    rows: Optional[list[dict]]
    error: Optional[str]
    fix_attempts: int

    result: Optional[str]
