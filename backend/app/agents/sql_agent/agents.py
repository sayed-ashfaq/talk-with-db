from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.main_agent.state import AgentState
from app.agents.sql_agent import db, sql
from app.agents.sql_agent.state import SQLAgentState
from app.core.exceptions import DestructiveSQLError, NL2SQLError
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration
from app.prompts.sql_agent import FIXER_PROMPT, GENERATION_PROMPT, SYNTHESIZER_PROMPT

MAX_FIX_ATTEMPTS = 3

logger = get_logger(__name__)


def generate_node(state: SQLAgentState) -> dict:
    prompt = GENERATION_PROMPT.format(db_type=state["db_type"], schema=state["schema_text"])
    with log_duration("SQL generation"):
        response = get_llm("sql_agent").invoke([SystemMessage(content=prompt), HumanMessage(content=state["refined_query"])])
    return {"sql_draft": response.content}


def execute_node(state: SQLAgentState) -> dict:
    try:
        with log_duration("SQL execution"):
            cleaned, rows = sql.clean_and_execute(state["sql_draft"], state["db_type"])
        logger.info("executed SQL: %s", cleaned)
        return {"cleaned_sql": cleaned, "rows": rows, "error": None, "blocked_reason": None}
    except DestructiveSQLError as exc:
        logger.info("blocked a write/destructive query attempt: %s", exc)
        return {"blocked_reason": str(exc), "error": None}
    except NL2SQLError as exc:
        logger.info("SQL attempt failed: %s", exc)
        return {"error": str(exc)}


def fix_node(state: SQLAgentState) -> dict:
    prompt = FIXER_PROMPT.format(db_type=state["db_type"], schema=state["schema_text"])
    context = (
        f"Original request: {state['refined_query']}\n\n"
        f"Previous SQL attempt:\n{state['sql_draft']}\n\n"
        f"Error:\n{state['error']}"
    )
    with log_duration("SQL fix attempt"):
        response = get_llm("sql_agent").invoke([SystemMessage(content=prompt), HumanMessage(content=context)])
    return {"sql_draft": response.content, "fix_attempts": state.get("fix_attempts", 0) + 1}


def route_after_execute(state: SQLAgentState) -> Literal["synthesize", "fix", "give_up"]:
    if state.get("error") is None:
        return "synthesize"
    if state.get("fix_attempts", 0) >= MAX_FIX_ATTEMPTS:
        return "give_up"
    return "fix"


def synthesize_node(state: SQLAgentState) -> dict:
    if state.get("blocked_reason"):
        context = (
            f"Question: {state['refined_query']}\n\n"
            f"This request would require modifying the database rather than just reading from "
            f"it ({state['blocked_reason']}), which is not permitted. Explain this limitation to "
            f"the user."
        )
    else:
        context = f"Question: {state['refined_query']}\n\nSQL used: {state['cleaned_sql']}\n\nResult rows: {state['rows']}"
    with log_duration("Response synthesis"):
        response = get_llm("sql_agent").invoke([SystemMessage(content=SYNTHESIZER_PROMPT), HumanMessage(content=context)])
    return {"result": response.content}


def give_up_node(state: SQLAgentState) -> dict:
    return {
        "result": (
            f"I couldn't produce a working query for this after {state.get('fix_attempts', 0)} "
            f"attempts. Last error: {state.get('error')}"
        )
    }


def _build_subgraph():
    graph = StateGraph(SQLAgentState)

    graph.add_node("generate", generate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("fix", fix_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("give_up", give_up_node)

    graph.add_edge(START, "generate")
    graph.add_edge("generate", "execute")
    graph.add_conditional_edges(
        "execute", route_after_execute, {"synthesize": "synthesize", "fix": "fix", "give_up": "give_up"}
    )
    graph.add_edge("fix", "execute")
    graph.add_edge("synthesize", END)
    graph.add_edge("give_up", END)

    return graph.compile()


_subgraph = _build_subgraph()


def sql_agent_node(state: AgentState) -> dict:
    connection = db.get_active()
    with log_duration("sql_agent total"):
        result = _subgraph.invoke(
            {
                "refined_query": state["refined_query"],
                "db_type": connection.db_type,
                "db_name": connection.dbname,
                "schema_text": db.get_active_schema_text(),
                "sql_draft": None,
                "cleaned_sql": None,
                "rows": None,
                "error": None,
                "blocked_reason": None,
                "fix_attempts": 0,
                "result": None,
            }
        )
    return {"agent_output": result["result"], "agent_sql": result.get("cleaned_sql")}
