"""Persistence for saved connections and schema annotations.

Everything here talks to *our* metadata store. Actually reaching out to a user's target database —
connecting, introspecting, running SQL — lives in app.agents.sql_agent.db, which this module calls
into but never the other way around.
"""

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sql_agent import db
from app.agents.sql_agent.db import SchemaContext
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import DatabaseConnectionError
from app.core.logging import get_logger
from app.db.models import SavedConnection, SchemaAnnotation

logger = get_logger(__name__)


async def save_connection(
    session: AsyncSession,
    name: str,
    db_type: db.DBType,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    url: Optional[str] = None,
) -> dict:
    sqlalchemy_url, resolved_dbname = db.resolve_url(db_type, host, port, user, password, dbname, url)
    # connect before inserting: a connection we can't reach isn't worth saving, and this surfaces
    # bad credentials as an error on the save itself rather than on some later activate
    connection = await db.build_connection(db_type, sqlalchemy_url, resolved_dbname)

    row = SavedConnection(
        name=name,
        db_type=db_type,
        url_encrypted=encrypt(sqlalchemy_url),
        dbname=resolved_dbname,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DatabaseConnectionError(f"a connection named '{name}' already exists") from exc

    db.set_active(connection, row.id)
    logger.info("saved and activated connection '%s' (id=%s)", name, row.id)
    return {"id": row.id, "name": name, "db_type": db_type, "dbname": resolved_dbname}


async def list_connections(session: AsyncSession) -> list[dict]:
    rows = (await session.scalars(select(SavedConnection).order_by(SavedConnection.created_at))).all()
    active_id = db.get_active_id()
    return [
        {
            "id": row.id,
            "name": row.name,
            "db_type": row.db_type,
            "dbname": row.dbname,
            "active": row.id == active_id,
        }
        for row in rows
    ]


async def activate_connection(session: AsyncSession, connection_id: uuid.UUID) -> dict:
    row = await session.get(SavedConnection, connection_id)
    if row is None:
        raise DatabaseConnectionError(f"no saved connection with id {connection_id}")

    connection = await db.build_connection(row.db_type, decrypt(row.url_encrypted), row.dbname)
    db.set_active(connection, row.id)
    logger.info("activated connection '%s' (id=%s)", row.name, row.id)
    return {"id": row.id, "name": row.name, "db_type": row.db_type, "dbname": row.dbname}


async def delete_connection(session: AsyncSession, connection_id: uuid.UUID) -> None:
    await session.execute(delete(SavedConnection).where(SavedConnection.id == connection_id))
    await session.commit()

    if db.get_active_id() == connection_id:
        db.clear_active()
    logger.info("deleted connection id=%s", connection_id)


def _annotation_to_dict(row: SchemaAnnotation) -> dict:
    return {
        "id": row.id,
        "connection_id": row.connection_id,
        "schema_name": row.schema_name or None,
        "table_name": row.table_name,
        "column_name": row.column_name or None,
        "comment": row.comment,
        "updated_at": row.updated_at,
    }


async def list_annotations(session: AsyncSession, connection_id: uuid.UUID) -> list[dict]:
    rows = await session.scalars(
        select(SchemaAnnotation).where(SchemaAnnotation.connection_id == connection_id)
    )
    return [_annotation_to_dict(row) for row in rows]


async def _annotations_map(session: AsyncSession, connection_id: Optional[uuid.UUID]) -> dict[tuple[str, str], str]:
    """(qualified_table_name, column_name) -> comment, column_name='' for a table-level comment.
    Keyed the same way render_schema_text looks things up."""
    if connection_id is None:
        return {}
    rows = await session.execute(
        select(
            SchemaAnnotation.schema_name,
            SchemaAnnotation.table_name,
            SchemaAnnotation.column_name,
            SchemaAnnotation.comment,
        ).where(SchemaAnnotation.connection_id == connection_id)
    )
    return {
        (db.qualify(schema_name or None, table_name), column_name): comment
        for schema_name, table_name, column_name, comment in rows
    }


async def upsert_annotation(
    session: AsyncSession,
    connection_id: uuid.UUID,
    table_name: str,
    comment: str,
    schema_name: Optional[str] = None,
    column_name: Optional[str] = None,
) -> dict:
    if await session.get(SavedConnection, connection_id) is None:
        raise DatabaseConnectionError(f"no saved connection with id {connection_id}")

    _validate_against_active(connection_id, table_name, schema_name, column_name)

    row = await session.scalar(
        select(SchemaAnnotation).where(
            SchemaAnnotation.connection_id == connection_id,
            SchemaAnnotation.schema_name == (schema_name or ""),
            SchemaAnnotation.table_name == table_name,
            SchemaAnnotation.column_name == (column_name or ""),
        )
    )
    if row is None:
        row = SchemaAnnotation(
            connection_id=connection_id,
            schema_name=schema_name or "",
            table_name=table_name,
            column_name=column_name or "",
            comment=comment,
        )
        session.add(row)
    else:
        row.comment = comment  # updated_at refreshes itself via the column's onupdate

    await session.commit()
    await session.refresh(row)
    return _annotation_to_dict(row)


def _validate_against_active(
    connection_id: uuid.UUID,
    table_name: str,
    schema_name: Optional[str],
    column_name: Optional[str],
) -> None:
    """Best-effort check against the live schema: if this connection happens to be the active one,
    catch a wrong/missing schema_name now — e.g. forgetting schema_name='public' on postgres —
    instead of silently writing a comment that will never match anything in render_schema_text.
    A connection that isn't active has no loaded schema, so there is nothing to check it against."""
    active = db.peek_active()
    if active is None or db.get_active_id() != connection_id:
        return

    qualified = db.qualify(schema_name, table_name)
    table = active.tables.get(qualified)
    if table is None:
        raise DatabaseConnectionError(
            f"no table '{qualified}' in the active connection's schema — table names are "
            f"schema-qualified for postgres (e.g. schema_name='public', table_name='rental')"
        )
    if column_name and column_name not in {c.name for c in table.columns}:
        raise DatabaseConnectionError(f"no column '{column_name}' on table '{qualified}'")


async def delete_annotation(session: AsyncSession, connection_id: uuid.UUID, annotation_id: uuid.UUID) -> None:
    result = await session.execute(
        delete(SchemaAnnotation).where(
            SchemaAnnotation.id == annotation_id,
            SchemaAnnotation.connection_id == connection_id,
        )
    )
    if result.rowcount == 0:
        raise DatabaseConnectionError(f"no annotation with id {annotation_id} for connection {connection_id}")
    await session.commit()


async def get_active_schema_text(session: AsyncSession) -> str:
    """Schema of the active connection, annotations merged in. Raises if nothing is active."""
    connection = db.get_active()
    annotations = await _annotations_map(session, db.get_active_id())
    return db.render_schema_text(connection.tables, annotations)


async def get_active_schema_context(session: AsyncSession) -> Optional[SchemaContext]:
    """Same as get_active_schema_text but returns None instead of raising when no connection is
    active — the chat endpoint resolves this for every message, including ones that never reach the
    SQL agent, so "no connection yet" must stay a valid state here."""
    connection = db.peek_active()
    if connection is None:
        return None
    annotations = await _annotations_map(session, db.get_active_id())
    return SchemaContext(
        db_type=connection.db_type,
        db_name=connection.dbname,
        schema_text=db.render_schema_text(connection.tables, annotations),
    )
