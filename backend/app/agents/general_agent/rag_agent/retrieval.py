"""Finding the chunks nearest a question, by cosine distance in embedding space.

Runs its own synchronous round trip against the metadata store rather than using the app's async
session — this is called from inside rag_agent_node, which runs on a worker thread already (see
app.router.chat), the same constraint and the same answer as sql_agent talking to a user's target
database synchronously: the graph is sync end to end, so nothing in it can await.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agents.general_agent.rag_agent.ingest import embed_text
from app.core.config import settings
from app.db.models import Document, DocumentChunk

TOP_K = 6

# a second engine, sync (psycopg2) rather than the app's async (asyncpg) one, pointed at the same
# database — see the module docstring for why a sync path is needed here at all.
# create_engine takes the URL object itself, never str(url) — URL.__str__ masks the password
# (renders it as "***"), which would silently produce a connection string that can't authenticate.
_sync_url = make_url(settings.metadata_database_url).set(drivername="postgresql+psycopg2")
_engine = create_engine(_sync_url, pool_pre_ping=True)


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    filename: str
    content: str


def retrieve(query: str, user_id: uuid.UUID, chat_id: uuid.UUID | None) -> list[RetrievedChunk]:
    """Top-k chunks from this user's library documents (chat_id IS NULL) plus this chat's own
    uploads — never another user's documents, and never another chat's chat-scoped ones."""
    query_vector = embed_text(query)
    with Session(_engine) as session:
        rows = session.execute(
            select(DocumentChunk.document_id, Document.filename, DocumentChunk.content)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == user_id)
            .where((Document.chat_id.is_(None)) | (Document.chat_id == chat_id))
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(TOP_K)
        ).all()

    return [RetrievedChunk(document_id=row[0], filename=row[1], content=row[2]) for row in rows]
