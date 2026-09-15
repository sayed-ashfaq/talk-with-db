"""Pandas/numpy analytics over an uploaded CSV — the General agent's counterpart to
database_agent.analytics_agent, built on the same closed vocabulary (app.agents.shared.analytics_ops)
instead of SQL result rows. The model picks operations, executor.py is the only thing that ever
calls pandas with them, so nothing model-authored runs as code.
"""

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.general_agent.csv_agent.prompts import PLAN_PROMPT, SYNTHESIZER_PROMPT
from app.agents.shared.analytics_ops.executor import AnalyticsPlanError, apply_plan
from app.agents.shared.analytics_ops.ops import AnalyticsPlan
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration

logger = get_logger(__name__)

NO_DATA = "I don't have a CSV to analyze yet — upload one to this chat and ask again."


def csv_agent_node(state: dict) -> dict:
    result = state.get("csv_context")
    if result is None or not result.rows:
        return {"agent_output": NO_DATA, "agent_sql": None}

    df = pd.DataFrame(result.rows, columns=result.columns)
    prompt = PLAN_PROMPT.format(columns=", ".join(result.columns), sample=df.head(3).to_dict(orient="records"))

    with log_duration("CSV analytics plan generation"):
        plan = get_llm("csv_agent").with_structured_output(AnalyticsPlan).invoke(
            [SystemMessage(content=prompt), HumanMessage(content=state["refined_query"])]
        )

    try:
        computed = apply_plan(df, plan)
    except AnalyticsPlanError as exc:
        logger.info("csv analytics plan rejected: %s", exc)
        return {"agent_output": f"I couldn't run that analysis: {exc}", "agent_sql": None}

    logger.info("csv analytics plan: %s", [op.op for op in plan.operations])

    context = (
        f"Question: {state['refined_query']}\n\n"
        f"What was computed: {plan.explanation}\n\n"
        f"Result:\n{computed.head(50).to_dict(orient='records')}"
    )
    with log_duration("CSV analytics synthesis"):
        response = get_llm("csv_agent").invoke(
            [SystemMessage(content=SYNTHESIZER_PROMPT), HumanMessage(content=context)]
        )

    return {
        "agent_output": response.content,
        "agent_sql": None,
        "result_rows": computed.to_dict(orient="records"),
        "result_columns": list(computed.columns),
        "result_truncated": False,
        # a stale chart from an earlier turn must not linger next to numbers it no longer
        # describes — same reasoning as database_agent.analytics_agent
        "chart_spec": None,
        "chart_profile": None,
    }
