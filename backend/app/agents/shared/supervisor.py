"""Reusable Command-based supervisor scaffold, shared by every top-level agent.

Extracted from what used to be one hardcoded graph in main_agent/main.py, once the app split into
separate Database and General agents. Same routing / resolved-check / finalize shape as before,
generalized over whichever specialists a given agent actually has — so the two agents are the same
*pattern*, not copy-pasted code.

Two shapes come out of build_agent_graph:
- With specialists: a supervisor LLM call picks a route, a specialist runs, the supervisor is asked
  again whether that resolved the question, up to max_attempts.
- With no specialists at all (e.g. the General agent before rag_agent/analytics_agent exist): there is only
  one possible destination, so a routing call every turn would be pure waste — go straight to the
  direct-response node.
"""

import logging
from enum import Enum
from typing import Callable, Literal, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import create_model

from app.core.llm import get_llm
from app.core.logging import log_duration

MAX_ATTEMPTS = 3


def _make_responder(agent_name: str, respond_prompt: str) -> Callable[[dict], dict]:
    def responder_node(state: dict) -> dict:
        llm = get_llm(agent_name)
        with log_duration("Direct response"):
            response = llm.invoke(
                [SystemMessage(content=respond_prompt), *state["chat_history"], HumanMessage(content=state["question"])]
            )
        return {"final_answer": response.content}

    return responder_node


def _finalize_node(state: dict) -> dict:
    logging.info("Final answer: %s", state["final_answer"])
    return {"chat_history": [HumanMessage(content=state["question"]), AIMessage(content=state["final_answer"])]}


def _build_direct_graph(state_type: type, agent_name: str, respond_prompt: str) -> CompiledStateGraph:
    graph = StateGraph(state_type)
    graph.add_node("responder", _make_responder(agent_name, respond_prompt))
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "responder")
    graph.add_edge("responder", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def build_agent_graph(
    *,
    state_type: type,
    agent_name: str,
    respond_prompt: str,
    specialists: Optional[dict[str, Callable[[dict], dict]]] = None,
    system_prompt: Optional[str] = None,
    max_attempts: int = MAX_ATTEMPTS,
    extra_finalize: Optional[Callable[[dict], dict]] = None,
) -> CompiledStateGraph:
    """Build one top-level agent's graph.

    `agent_name` is the get_llm() key both the routing decision and the direct response are made
    with — the same model handles both duties, matching how the pre-split main_agent worked.

    `extra_finalize`, when given, is called with the winning specialist's state at both finalize
    points (max-attempts-reached and resolved) and its return merged into the update — e.g. the
    Database agent uses this to carry `agent_sql` over as `final_sql`. Fields a specialist writes
    directly onto state (result_rows, chart_spec, ...) need no such handling: LangGraph's invoke()
    returns the whole accumulated state, not just finalize_node's output, so they're already there.
    """
    specialists = specialists or {}

    if not specialists:
        return _build_direct_graph(state_type, agent_name, respond_prompt)

    if system_prompt is None:
        raise ValueError("system_prompt is required when specialists are given")

    routes = [*specialists.keys(), "respond"]
    # a real enum, not a free-text field, so structured output gets a genuinely constrained schema —
    # matters more once the LLM backend is a smaller/local model, not just Groq
    RouteEnum = Enum(f"_{agent_name}_Routes", {route: route for route in routes})

    Decision = create_model(
        f"_{agent_name}_Decision",
        resolved=(Literal["yes", "no"], ...),
        next=(RouteEnum, ...),
        refined_query=(str, ...),
        reasoning=(str, ...),
    )

    def _decision_context(state: dict) -> list[AnyMessage]:
        context = [SystemMessage(content=system_prompt), *state["chat_history"], HumanMessage(content=state["question"])]
        if state.get("agent_output") is not None:
            context.append(AIMessage(content=f"[{state['next']} responded]: {state['agent_output']}"))
        return context

    def _finalize_update(state: dict) -> dict:
        update = {"final_answer": state["agent_output"]}
        if extra_finalize is not None:
            update.update(extra_finalize(state))
        return update

    def supervisor_node(state: dict) -> Command:
        attempted = state.get("agent_output") is not None

        if attempted and state.get("attempts", 0) >= max_attempts:
            return Command(goto="finalize", update=_finalize_update(state))

        with log_duration("Routing decision"):
            decision = get_llm(agent_name).with_structured_output(Decision).invoke(_decision_context(state))

        if attempted and decision.resolved == "yes":
            return Command(goto="finalize", update=_finalize_update(state))

        next_route = decision.next.value
        goto = "responder" if next_route == "respond" else next_route
        return Command(
            goto=goto,
            update={"next": next_route, "refined_query": decision.refined_query, "attempts": state.get("attempts", 0) + 1},
        )

    graph = StateGraph(state_type)
    graph.add_node("supervisor", supervisor_node)
    for name, node in specialists.items():
        graph.add_node(name, node)
        graph.add_edge(name, "supervisor")
    graph.add_node("responder", _make_responder(agent_name, respond_prompt))
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "supervisor")
    graph.add_edge("responder", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
