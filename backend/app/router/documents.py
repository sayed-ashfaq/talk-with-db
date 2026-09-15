"""Uploading and managing RAG documents.

Two entry points feed the same table: POST /documents with a chat_id uploads into that one chat
(only its own rag_agent calls can retrieve from it); omitting chat_id uploads into the user's
library, visible to every general chat they have. See app.services.documents for persistence and
app.agents.general_agent.rag_agent for what happens at retrieval time.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.agents.general_agent.rag_agent import ingest
from app.core.dependencies import CurrentUser
from app.core.exceptions import FileTooLargeError, NotAGeneralChatError, UnsupportedFileTypeError
from app.core.logging import get_logger, log_duration
from app.db.session import SessionDep
from app.services import chats as chat_service
from app.services import documents as document_service

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

# generous for a text-heavy PDF, small enough to bound memory and embedding time on one request
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    chat_id: Optional[uuid.UUID] = None
    chunk_count: int
    created_at: datetime


@router.post("", response_model=DocumentResponse)
async def upload_document(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    # omit for a library upload (the sidebar); pass to scope this upload to one chat instead
    chat_id: Optional[uuid.UUID] = Form(None),
) -> DocumentResponse:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("only PDF files are supported")

    if chat_id is not None:
        # 404s if the chat isn't theirs, before anything is parsed
        chat = await chat_service.get_owned_chat(session, user.id, chat_id)
        if chat.section != "general":
            raise NotAGeneralChatError

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError

    logger.info("user %s uploading document '%s' (chat_id=%s)", user.id, file.filename, chat_id)
    with log_duration("Document ingest"):
        # pypdf + fastembed are both CPU-bound — off the event loop, same reason schema
        # introspection and target-DB queries run in a thread elsewhere in this app
        chunks = await asyncio.to_thread(ingest.ingest_pdf, content)

    document = await document_service.create_document(
        session, user.id, filename=file.filename or "document.pdf", chat_id=chat_id, chunks=chunks
    )
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        chat_id=document.chat_id,
        chunk_count=len(chunks),
        created_at=document.created_at,
    )


@router.get("", response_model=list[DocumentResponse])
async def get_documents(
    user: CurrentUser, session: SessionDep, chat_id: Optional[uuid.UUID] = None
) -> list[DocumentResponse]:
    """chat_id omitted: the user's library. chat_id given: that one chat's own uploads."""
    if chat_id is not None:
        await chat_service.get_owned_chat(session, user.id, chat_id)  # 404s if not theirs
    return [
        DocumentResponse(**row) for row in await document_service.list_documents(session, user.id, chat_id)
    ]


@router.delete("/{document_id}")
async def remove_document(document_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> dict:
    await document_service.delete_document(session, user.id, document_id)
    return {"deleted": str(document_id)}
