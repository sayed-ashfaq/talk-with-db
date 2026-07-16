from langchain_core.messages import AIMessage

from app.agents.state import AgentState


def python_agent_node(state: AgentState) -> dict:
    return {
        "messages": [
            AIMessage(
                content="[python_agent] not wired up yet — this will turn data into "
                "charts (matplotlib)."
            )
        ]
    }
