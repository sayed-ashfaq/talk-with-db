from langchain_groq import ChatGroq

from app.core.config import settings

_GROQ_MODELS = {
    "main_agent": settings.main_agent_model,
    "sql_agent": settings.sql_agent_model,
    "visualizer": settings.visualizer_model,
    "analytics_agent": settings.analytics_agent_model,
    "rag_agent": settings.rag_agent_model,
    "csv_agent": settings.csv_agent_model,
    "websearch_agent": settings.websearch_agent_model,
}

# falls back to the groq model name when a local override isn't set, so a partial local setup
# doesn't need every agent pinned before it's usable
_LOCAL_MODELS = {
    "main_agent": settings.local_main_agent_model or settings.main_agent_model,
    "sql_agent": settings.local_sql_agent_model or settings.sql_agent_model,
    "visualizer": settings.local_visualizer_model or settings.visualizer_model,
    "analytics_agent": settings.local_analytics_agent_model or settings.analytics_agent_model,
    "rag_agent": settings.local_rag_agent_model or settings.rag_agent_model,
    "csv_agent": settings.local_csv_agent_model or settings.csv_agent_model,
    "websearch_agent": settings.local_websearch_agent_model or settings.websearch_agent_model,
}


def get_llm(agent: str, **kwargs):
    """One factory for every agent's model, switched by `settings.llm_provider` rather than by call
    site. Swapping to a local/on-prem model later is a config change here, not a change in every
    agent that calls this.
    """
    if settings.llm_provider == "local":
        model = _LOCAL_MODELS.get(agent)
        if model is None:
            raise ValueError(f"No local model configured for agent '{agent}'")
        # imported lazily so a groq-only setup never needs langchain-ollama installed
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, base_url=settings.local_llm_base_url, **kwargs)

    if settings.llm_provider != "groq":
        raise ValueError(f"Unknown llm_provider '{settings.llm_provider}' (expected 'groq' or 'local')")

    model = _GROQ_MODELS.get(agent)
    if model is None:
        raise ValueError(f"No model configured for agent '{agent}'")
    if not settings.groq_api_key:
        raise ValueError("llm_provider='groq' but GROQ_API_KEY is not set")

    # qwen3.x's reasoning_effort enum (none/default/minimal/low/medium/high/xhigh/max) isn't the
    # same one gpt-oss accepts (low/medium/high only, confirmed against the live API) — sending it
    # to a gpt-oss call 400s, so this is opt-in per model family rather than a blanket kwarg
    if model.startswith("qwen/") and "reasoning_effort" not in kwargs:
        kwargs["reasoning_effort"] = settings.reasoning_effort

    return ChatGroq(model=model, api_key=settings.groq_api_key, **kwargs)
