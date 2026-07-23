from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.agents.sql_agent.db import DbContext


class AgentState(TypedDict):
    chat_history: Annotated[list[AnyMessage], add_messages]

    # the requesting user's database, resolved by the router before the graph runs — agent nodes are
    # synchronous and can neither await the metadata store nor reach into the connection registry.
    # None when the user has no active connection.
    db_context: Optional[DbContext]

    question: str
    refined_query: str
    next: str
    agent_output: Optional[str]
    agent_sql: Optional[str]
    attempts: int

    final_answer: Optional[str]
    final_sql: Optional[str]
