from app.agents.main_agent.state import AgentState


def sql_agent_node(state: AgentState) -> dict:
    return {
        "agent_output": (
            f"[sql_agent] not wired up yet — routing works, NL2SQL generation is next up. "
            f"Refined query was: {state['refined_query']}"
        )
    }
