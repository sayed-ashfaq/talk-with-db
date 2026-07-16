from langchain_core.messages import AIMessage

from app.agents.state import AgentState


def knowledge_agent_node(state: AgentState) -> dict:
    return {
        "messages": [
            AIMessage(
                content="[knowledge_agent] not wired up yet — this will search the web "
                "(Tavily) and any provided database for context."
            )
        ]
    }
