"""Wires the General agent's graph. No specialists yet (rag_agent/csv_agent land in Phase 2), so
build_agent_graph builds the direct-response shape: every message goes straight to the responder —
a real, working general assistant today, not a placeholder, with no LLM call spent choosing between
routes that don't exist yet.

Deliberately never receives a db_context or any other database-shaped state: that's what makes the
privacy boundary between this agent and the Database agent structural rather than a prompting
convention — see app/router/chat.py, which never resolves a DB connection for a "general" chat.
"""

from app.agents.general_agent.state import GeneralAgentState
from app.agents.shared.supervisor import build_agent_graph
from app.agents.general_agent.prompts import RESPOND_PROMPT

graph = build_agent_graph(
    state_type=GeneralAgentState,
    agent_name="main_agent",
    respond_prompt=RESPOND_PROMPT,
)
