"""Conversation history: the sidebar list, and opening or managing one chat.

Sending a message lives in app.router.chat — it belongs with the agent invocation rather than here.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

from app.agents.general_agent import loader as csv_loader
from app.core.dependencies import CurrentUser
from app.core.exceptions import FileTooLargeError, NotAGeneralChatError, UnsupportedFileTypeError
from app.core.logging import get_logger, log_duration
from app.db.session import SessionDep
from app.router.chat import MessageResponse
from app.services import chats as chat_service
from app.services import csv_uploads as csv_upload_service

router = APIRouter(prefix="/chats", tags=["chats"])
logger = get_logger(__name__)

# generous for a real spreadsheet, small enough to bound memory on one request
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class ChatSummary(BaseModel):
    id: uuid.UUID
    title: str
    connection_id: Optional[uuid.UUID] = None
    section: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatDetail(BaseModel):
    id: uuid.UUID
    title: str
    connection_id: Optional[uuid.UUID] = None
    section: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]


class RenameChatRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class CreateChatRequest(BaseModel):
    section: Literal["general", "database"] = "general"
    # e.g. an attached file's name, so the sidebar shows something more useful than "New chat"
    # until the first real message renames it. Falls back to "New chat" like any chat would.
    title: Optional[str] = None


@router.get("", response_model=list[ChatSummary])
async def get_chats(user: CurrentUser, session: SessionDep) -> list[ChatSummary]:
    """Most recently used first — the order a sidebar wants."""
    return [ChatSummary(**row) for row in await chat_service.list_chats(session, user.id)]


@router.post("", response_model=ChatSummary)
async def create_chat(
    request: CreateChatRequest, user: CurrentUser, session: SessionDep
) -> ChatSummary:
    """A chat with no first message yet.

    POST /chat still refuses an empty message — a chat can't be *started* by silence — but a file
    attached before anything is typed needs a chat_id to upload into (both upload routes require
    one), so this is the one path that creates a chat without a message. Unlike a chat POST /chat
    starts, nothing here re-derives the title from the first real message that follows — it keeps
    whatever `title` was given (typically the attached file's name) until the user renames it.
    """
    connection_id = user.active_connection_id if request.section == "database" else None
    chat = await chat_service.create_chat(
        session,
        user.id,
        title=(request.title or "New chat")[:255],
        connection_id=connection_id,
        section=request.section,
    )
    await session.commit()
    return ChatSummary(**await chat_service.summarise(session, chat))


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ChatDetail:
    chat = await chat_service.get_chat_with_messages(session, user.id, chat_id)
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        connection_id=chat.connection_id,
        section=chat.section,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        # with_data: this is the reopening path, and the chart is the part of an old answer worth
        # coming back to
        messages=[MessageResponse.of(m, with_data=True) for m in chat.messages],
    )


@router.patch("/{chat_id}", response_model=ChatSummary)
async def rename_chat(
    chat_id: uuid.UUID, request: RenameChatRequest, user: CurrentUser, session: SessionDep
) -> ChatSummary:
    chat = await chat_service.rename_chat(session, user.id, chat_id, request.title)
    return ChatSummary(**await chat_service.summarise(session, chat))


@router.delete("/{chat_id}")
async def remove_chat(chat_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> dict:
    await chat_service.delete_chat(session, user.id, chat_id)
    return {"deleted": str(chat_id)}


class CsvUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    row_count: int
    truncated: bool
    created_at: datetime


@router.post("/{chat_id}/csv", response_model=CsvUploadResponse)
async def upload_csv(
    chat_id: uuid.UUID, user: CurrentUser, session: SessionDep, file: UploadFile = File(...)
) -> CsvUploadResponse:
    """Replaces nothing — analytics_agent always reads the most recent upload for this chat (see
    app.services.csv_uploads.load_latest), so re-uploading is just uploading again."""
    chat = await chat_service.get_owned_chat(session, user.id, chat_id)  # 404s if not theirs
    if chat.section != "general":
        raise NotAGeneralChatError

    if not (file.filename or "").lower().endswith(".csv"):
        raise UnsupportedFileTypeError("only CSV files are supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError

    logger.info("user %s uploading CSV '%s' to chat %s", user.id, file.filename, chat_id)
    with log_duration("CSV parse"):
        result = await asyncio.to_thread(csv_loader.parse_csv, content)

    upload = await csv_upload_service.create_csv_upload(
        session, user.id, chat_id, filename=file.filename or "data.csv", result=result
    )
    return CsvUploadResponse(
        id=upload.id,
        filename=upload.filename,
        row_count=len(result.rows),
        truncated=result.truncated,
        created_at=upload.created_at,
    )
