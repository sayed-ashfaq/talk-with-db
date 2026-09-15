"""Answering from a live web search — the one General-agent specialist that reaches outside the
environment. See the Phase 2 privacy design note: this exists because query text and results both
cross to a third party, which was accepted for the current sample-data build phase and will need
revisiting before any client data flows through this app.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.general_agent.websearch import tavily_client
from app.agents.general_agent.websearch.prompts import SYNTHESIZER_PROMPT
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration

logger = get_logger(__name__)

NO_RESULTS = (
    "I couldn't find anything useful searching the web for that — web search may not be configured "
    "on this server, or the search itself came back empty."
)


def websearch_agent_node(state: dict) -> dict:
    with log_duration("Web search"):
        results = tavily_client.search(state["refined_query"])

    if not results:
        return {"agent_output": NO_RESULTS}

    logger.info("web search returned %d result(s)", len(results))
    context = "\n\n".join(f"[{r.title}]({r.url})\n{r.content}" for r in results)

    with log_duration("Web search synthesis"):
        response = get_llm("websearch_agent").invoke(
            [
                SystemMessage(content=SYNTHESIZER_PROMPT),
                HumanMessage(content=f"Question: {state['refined_query']}\n\nSearch results:\n{context}"),
            ]
        )

    return {"agent_output": response.content}
