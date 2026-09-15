"""Answering from a user's uploaded documents — never a fresh web search, never anything not
actually retrieved. See retrieval.py for how chunks are found and ingest.py for how they got there.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.general_agent.rag_agent import retrieval
from app.agents.general_agent.rag_agent.prompts import SYNTHESIZER_PROMPT
from app.core.llm import get_llm
from app.core.logging import get_logger, log_duration

logger = get_logger(__name__)

NO_DOCS = (
    "I don't have any documents to search yet — upload a PDF from this chat, or from the documents "
    "sidebar, and ask again."
)


def rag_agent_node(state: dict) -> dict:
    with log_duration("Document retrieval"):
        chunks = retrieval.retrieve(state["refined_query"], state["user_id"], state.get("chat_id"))

    if not chunks:
        return {"agent_output": NO_DOCS}

    logger.info(
        "retrieved %d chunk(s) from %d document(s)", len(chunks), len({c.document_id for c in chunks})
    )
    context = "\n\n".join(f"[{chunk.filename}]\n{chunk.content}" for chunk in chunks)

    with log_duration("RAG synthesis"):
        response = get_llm("rag_agent").invoke(
            [
                SystemMessage(content=SYNTHESIZER_PROMPT),
                HumanMessage(content=f"Question: {state['refined_query']}\n\nRetrieved passages:\n{context}"),
            ]
        )

    return {"agent_output": response.content}
