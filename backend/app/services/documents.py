"""Persistence for uploaded documents (RAG) — the async CRUD side, used by the upload/list/delete
endpoints. Retrieval itself is a different code path: app.agents.general_agent.rag_agent.retrieval
runs its own synchronous query from inside the agent graph, for the same reason
app.agents.database_agent.sql_agent.db talks to a user's target database synchronously rather than
through this module.

Scoped like everything else here: every function takes the signed-in user and filters on their id.
"""

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentNotFoundError
from app.db.models import Document, DocumentChunk


async def create_document(
    session: AsyncSession,
    user_id: uuid.UUID,
    filename: str,
    chat_id: Optional[uuid.UUID],
    chunks: list[tuple[str, list[float]]],
) -> Document:
    document = Document(user_id=user_id, chat_id=chat_id, filename=filename)
    session.add(document)
    await session.flush()  # assigns document.id without ending the transaction

    session.add_all(
        DocumentChunk(document_id=document.id, chunk_index=i, content=content, embedding=embedding)
        for i, (content, embedding) in enumerate(chunks)
    )
    await session.commit()
    await session.refresh(document)
    return document


def _summary(document: Document, chunk_count: int) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "chat_id": document.chat_id,
        "chunk_count": chunk_count,
        "created_at": document.created_at,
    }


async def list_documents(
    session: AsyncSession, user_id: uuid.UUID, chat_id: Optional[uuid.UUID] = None
) -> list[dict]:
    """chat_id=None lists only the user's library documents (the sidebar view); passing a chat_id
    lists that chat's own uploads instead — the two are never mixed in one listing, matching how
    retrieval itself treats them as separate sets unioned only at query time.
    """
    chunk_count = (
        select(func.count(DocumentChunk.id))
        .where(DocumentChunk.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(Document, chunk_count.label("chunk_count"))
            .where(Document.user_id == user_id, Document.chat_id == chat_id)
            .order_by(Document.created_at.desc())
        )
    ).all()
    return [_summary(doc, count) for doc, count in rows]


async def delete_document(session: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
    document = await session.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    if document is None:
        raise DocumentNotFoundError
    await session.delete(document)  # chunks follow by cascade
    await session.commit()
