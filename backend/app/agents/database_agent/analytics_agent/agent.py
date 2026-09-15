"""Pandas/numpy analytics over rows already in this conversation — never a fresh query.

The model picks operations from shared.analytics_ops.ops's closed vocabulary; executor.py is the
only thing that ever calls pandas with them, so nothing model-authored runs as code. Mirrors
visualizer/agent.py's shape: reads rows already fetched (this turn's result_rows, or an earlier
turn's prior_result), never talks to the target database itself.
"""

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.database_agent.analytics_agent.prompts import PLAN_PROMPT, SYNTHESIZER_PROMPT
from app.agents.shared.analytics_ops.executor import AnalyticsPlanError, apply_plan
from app.agents.shared.analytics_ops.ops import AnalyticsPlan
from app.agents.shared.tabular import QueryResult
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration

logger = get_logger(__name__)

NO_DATA = (
    "I don't have any query results to analyze yet — nothing has been fetched in this conversation. "
    "Ask for the data you want first and I can run the numbers on it."
)


def _rows(state: dict) -> QueryResult | None:
    """This turn's result if sql_agent already ran once (the supervisor's retry loop handing off
    after a first hop), otherwise the last turn's — same "already fetched" rule visualizer follows.
    """
    if state.get("result_rows") is not None:
        return QueryResult(
            columns=state.get("result_columns") or [],
            rows=state["result_rows"],
            truncated=bool(state.get("result_truncated")),
        )
    return state.get("prior_result")


def analytics_agent_node(state: dict) -> dict:
    result = _rows(state)
    if result is None or not result.rows:
        return {"agent_output": NO_DATA, "agent_sql": None}

    df = pd.DataFrame(result.rows, columns=result.columns)
    prompt = PLAN_PROMPT.format(columns=", ".join(result.columns), sample=df.head(3).to_dict(orient="records"))

    with log_duration("Analytics plan generation"):
        plan = get_llm("analytics_agent").with_structured_output(AnalyticsPlan).invoke(
            [SystemMessage(content=prompt), HumanMessage(content=state["refined_query"])]
        )

    try:
        computed = apply_plan(df, plan)
    except AnalyticsPlanError as exc:
        logger.info("analytics plan rejected: %s", exc)
        return {"agent_output": f"I couldn't run that analysis: {exc}", "agent_sql": None}

    logger.info("analytics plan: %s", [op.op for op in plan.operations])

    context = (
        f"Question: {state['refined_query']}\n\n"
        f"What was computed: {plan.explanation}\n\n"
        f"Result:\n{computed.head(50).to_dict(orient='records')}"
    )
    with log_duration("Analytics synthesis"):
        response = get_llm("analytics_agent").invoke(
            [SystemMessage(content=SYNTHESIZER_PROMPT), HumanMessage(content=context)]
        )

    return {
        "agent_output": response.content,
        "agent_sql": None,
        "result_rows": computed.to_dict(orient="records"),
        "result_columns": list(computed.columns),
        "result_truncated": False,
        # a stale chart from an earlier turn must not linger next to numbers it no longer describes —
        # charting this result is a normal follow-up turn away, same as any other "show that as a
        # chart" ask, once it's persisted and read back as prior_result
        "chart_spec": None,
        "chart_profile": None,
    }
