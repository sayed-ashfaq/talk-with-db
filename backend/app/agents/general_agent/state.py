from app.agents.shared.state import BaseAgentState


class GeneralAgentState(BaseAgentState):
    """Nothing beyond the shared base yet — rag_agent/csv_agent context (retrieved chunks, the
    active uploaded CSV) lands here once those specialists exist."""
