"""Every model must be imported here — Alembic autogenerate only sees tables that have been
registered on Base.metadata by import time, and env.py imports just this package."""

from app.db.models.connection import SavedConnection, SchemaAnnotation

__all__ = ["SavedConnection", "SchemaAnnotation"]
