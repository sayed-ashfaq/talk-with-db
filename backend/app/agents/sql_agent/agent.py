from langchain_core.messages import AIMessage

from app.agents.main_agent.state import AgentState


def sql_agent_node(state: AgentState) -> dict:
    return {
        "messages": [
            AIMessage(
                content="[sql_agent] not wired up yet — routing works, "
                "NL2SQL generation is next up."
            )
        ]
    }
