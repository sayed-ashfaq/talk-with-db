"""Every model must be imported here — Alembic autogenerate only sees tables that have been
registered on Base.metadata by import time, and env.py imports just this package."""

from app.db.models.chat import Chat, Message
from app.db.models.connection import SavedConnection, SchemaAnnotation
from app.db.models.csv_upload import CsvUpload
from app.db.models.document import Document, DocumentChunk
from app.db.models.user import OAuthAccount, Session, User

__all__ = [
    "Chat",
    "CsvUpload",
    "Document",
    "DocumentChunk",
    "Message",
    "OAuthAccount",
    "SavedConnection",
    "SchemaAnnotation",
    "Session",
    "User",
]
