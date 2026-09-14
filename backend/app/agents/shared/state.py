"""State every top-level agent shares, regardless of which specialists it has.

Each agent (database_agent, general_agent, ...) extends this with whatever extra fields its own
specialists need — see e.g. app.agents.database_agent.state.DatabaseAgentState.
"""

from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class BaseAgentState(TypedDict):
    chat_history: Annotated[list[AnyMessage], add_messages]

    question: str
    refined_query: str
    next: str
    agent_output: Optional[str]
    attempts: int

    final_answer: Optional[str]
