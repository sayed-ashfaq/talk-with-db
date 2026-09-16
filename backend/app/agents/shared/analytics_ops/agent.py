"""The analytics specialist's node logic — pandas/numpy/scipy computation over a table already in
hand, never a fresh query. One implementation serves both the General agent (an uploaded CSV) and
the Database agent (rows already fetched this conversation): the model picks operations from
ops.py's closed vocabulary, executor.py is the only thing that ever calls pandas with them, so
nothing model-authored runs as code.

Only three things differ per caller, so they're the factory's parameters: where the table comes
from, which model answers, and whether that model needs Groq's json_mode instead of the default
tool-calling structured output (see JSON_MODE_INSTRUCTIONS for why that's sometimes necessary).
"""

from typing import Callable, Optional

import pandas as pd
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.agents.shared.analytics_ops.executor import AnalyticsPlanError, apply_plan
from app.agents.shared.analytics_ops.ops import AnalyticsPlan
from app.agents.shared.analytics_ops.prompts import JSON_MODE_INSTRUCTIONS, PLAN_PROMPT, SYNTHESIZER_PROMPT
from app.agents.shared.tabular import QueryResult
from app.agents.shared.visualizer import charts
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration

logger = get_logger(__name__)

GetData = Callable[[dict], Optional[QueryResult]]


def make_analytics_agent_node(
    *, get_data: GetData, no_data_message: str, llm_key: str, json_mode: bool = False
) -> Callable[[dict], dict]:
    """Build the analytics specialist node for one caller.

    `get_data` reads whatever this caller considers "the table already in hand" out of state — an
    uploaded CSV for the General agent, fetched query rows (or an earlier turn's prior_result) for
    the Database agent.

    `llm_key` is the get_llm() config key for this caller's model, kept per-caller rather than
    hardcoded here so the General and Database agents can keep running different models (they do
    today) or be pointed at the same one later, purely as a config change.
    """

    def analytics_agent_node(state: dict) -> dict:
        result = get_data(state)
        if result is None or not result.rows:
            return {"agent_output": no_data_message, "agent_sql": None}

        df = pd.DataFrame(result.rows, columns=result.columns)
        prompt = PLAN_PROMPT.format(columns=", ".join(result.columns), sample=df.head(3).to_dict(orient="records"))
        if json_mode:
            prompt += JSON_MODE_INSTRUCTIONS

        llm = get_llm(llm_key)
        if json_mode:
            structured_llm = llm.with_structured_output(AnalyticsPlan, method="json_mode")
        else:
            structured_llm = llm.with_structured_output(AnalyticsPlan)

        with log_duration("Analytics plan generation"):
            try:
                plan = structured_llm.invoke(
                    [SystemMessage(content=prompt), HumanMessage(content=state["refined_query"])]
                )
            except (OutputParserException, ValidationError) as exc:
                # the model's own output didn't match AnalyticsPlan's schema (wrong/missing field,
                # invalid enum value, ...) — a bad answer from the model, not a bug here, so this
                # gets the same graceful handling as a plan that parsed but referenced a bad column
                logger.info("analytics plan generation failed to parse: %s", exc)
                return {
                    "agent_output": "I couldn't figure out how to compute that — try rephrasing the question.",
                    "agent_sql": None,
                }

        logger.info("analytics plan: %s", [op.op for op in plan.operations])

        try:
            computed = apply_plan(df, plan)
        except AnalyticsPlanError as exc:
            logger.info("analytics plan rejected: %s", exc)
            return {"agent_output": f"I couldn't run that analysis: {exc}", "agent_sql": None}

        computed_rows = computed.to_dict(orient="records")
        row_count = len(computed_rows)
        sample = computed_rows[:50]
        context = (
            f"Question: {state['refined_query']}\n\n"
            f"What was computed: {plan.explanation}\n\n"
            f"Total rows in the result: {row_count}\n\n"
            f"Sample rows (first {len(sample)} of {row_count}):\n{sample}"
        )
        with log_duration("Analytics synthesis"):
            response = get_llm(llm_key).invoke([SystemMessage(content=SYNTHESIZER_PROMPT), HumanMessage(content=context)])

        # code decides whether this result can honestly be charted at all (candidates() below
        # MIN_ROWS or with no numeric column returns none, no LLM call spent); the model only gets
        # a say when more than one valid chart is on the table — same split sql_agent's own
        # auto-chart uses, so a computed result and a queried one behave identically here
        chart_spec, chart_profile = charts.select(
            state["refined_query"], QueryResult(columns=list(computed.columns), rows=computed_rows, truncated=False)
        )
        if chart_spec:
            logger.info("analytics chart: %s of %s by %s", chart_spec.type.value, ", ".join(chart_spec.y), chart_spec.x)

        return {
            "agent_output": response.content,
            "agent_sql": None,
            "result_rows": computed_rows,
            "result_columns": list(computed.columns),
            "result_truncated": False,
            "chart_spec": chart_spec,
            "chart_profile": chart_profile,
        }

    return analytics_agent_node
