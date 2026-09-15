import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CsvUpload(Base):
    """A CSV uploaded into one chat, parsed once at upload time rather than re-read from disk on
    every turn. Chat-scoped only — unlike documents there is no library concept for CSVs (see the
    Phase 2 design decision). csv_agent operates on the most recent upload for its chat, the same
    "most recent wins" rule sql_agent's prior_result already follows.
    """

    __tablename__ = "csv_uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    columns: Mapped[list] = mapped_column(JSONB)
    rows: Mapped[list] = mapped_column(JSONB)
    truncated: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
