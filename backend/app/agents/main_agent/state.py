from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    chat_history: Annotated[list[AnyMessage], add_messages]

    question: str
    refined_query: str
    next: str
    agent_output: Optional[str]
    agent_sql: Optional[str]
    attempts: int

    final_answer: Optional[str]
    final_sql: Optional[str]
