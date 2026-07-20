from app.agents.main_agent.state import AgentState


def python_agent_node(state: AgentState) -> dict:
    return {
        "agent_output": (
            f"[python_agent] not wired up yet — this will turn data into charts (matplotlib). "
            f"Refined query was: {state['refined_query']}"
        ),
        "agent_sql": None,
    }
