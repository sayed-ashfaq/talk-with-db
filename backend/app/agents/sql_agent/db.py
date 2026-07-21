from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    inspect,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import DatabaseConnectionError, SQLExecutionError
from app.core.logging import get_logger

logger = get_logger(__name__)

DBType = Literal["postgres", "mysql"]

_DRIVER = {
    "postgres": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
}

MAX_ROWS = 500
QUERY_TIMEOUT_MS = 10_000


@dataclass
class ColumnSchema:
    name: str
    type: str
    pk: bool


@dataclass
class ForeignKeySchema:
    columns: list[str]
    referred_table: str
    referred_columns: list[str]


@dataclass
class TableSchema:
    name: str  # qualified, e.g. "sales.customer"
    columns: list[ColumnSchema] = field(default_factory=list)
    foreign_keys: list[ForeignKeySchema] = field(default_factory=list)


@dataclass
class Connection:
    engine: Engine
    db_type: DBType
    dbname: str
    tables: dict[str, TableSchema]  # structural data only — expensive, cached for the connection's life


_active: Optional[Connection] = None
_active_id: Optional[int] = None

# --- metadata store: saved connection configs live in our own postgres, separate from any target DB ---

_meta_engine = create_engine(settings.metadata_database_url, pool_pre_ping=True)
_metadata = MetaData()

saved_connections = Table(
    "saved_connections",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, unique=True, nullable=False),
    Column("db_type", String, nullable=False),
    Column("url_encrypted", String, nullable=False),
    Column("dbname", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# schema/column comments a user attaches by hand — kept separate from `tables` above because
# they're cheap to write and must take effect immediately, without re-introspecting the (possibly
# remote) target database. column_name='' means the comment is on the table itself, not a column.
schema_annotations = Table(
    "schema_annotations",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("connection_id", Integer, ForeignKey("saved_connections.id", ondelete="CASCADE"), nullable=False),
    Column("schema_name", String, nullable=False, server_default=""),
    Column("table_name", String, nullable=False),
    Column("column_name", String, nullable=False, server_default=""),
    Column("comment", String, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("connection_id", "schema_name", "table_name", "column_name", name="uq_schema_annotations_key"),
)

_metadata.create_all(_meta_engine)


def _resolve_url(
    db_type: DBType,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    url: Optional[str] = None,
) -> tuple[str, str]:
    if url:
        parsed = make_url(url).set(drivername=_DRIVER[db_type])
        return parsed.render_as_string(hide_password=False), parsed.database

    if not all([host, port, user, password, dbname]):
        raise ValueError("provide either 'url', or all of host/port/user/password/dbname")
    return f"{_DRIVER[db_type]}://{user}:{password}@{host}:{port}/{dbname}", dbname


def _build_connection(db_type: DBType, sqlalchemy_url: str, dbname: str) -> Connection:
    engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:
        raise DatabaseConnectionError(f"could not connect to {db_type} database '{dbname}'") from exc

    tables = _introspect(engine)
    logger.info("connected to %s database '%s' — %d table(s) found", db_type, dbname, len(tables))
    return Connection(engine=engine, db_type=db_type, dbname=dbname, tables=tables)


def save_connection(
    name: str,
    db_type: DBType,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    url: Optional[str] = None,
) -> dict:
    global _active, _active_id

    sqlalchemy_url, resolved_dbname = _resolve_url(db_type, host, port, user, password, dbname, url)
    connection = _build_connection(db_type, sqlalchemy_url, resolved_dbname)

    try:
        with _meta_engine.begin() as conn:
            result = conn.execute(
                insert(saved_connections).values(
                    name=name,
                    db_type=db_type,
                    url_encrypted=encrypt(sqlalchemy_url),
                    dbname=resolved_dbname,
                    created_at=datetime.now(timezone.utc),
                )
            )
            connection_id = result.inserted_primary_key[0]
    except IntegrityError as exc:
        raise DatabaseConnectionError(f"a connection named '{name}' already exists") from exc

    _active = connection
    _active_id = connection_id
    logger.info("saved and activated connection '%s' (id=%s)", name, connection_id)
    return {"id": connection_id, "name": name, "db_type": db_type, "dbname": resolved_dbname}


def list_connections() -> list[dict]:
    with _meta_engine.connect() as conn:
        rows = conn.execute(select(saved_connections)).mappings().all()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "db_type": row["db_type"],
            "dbname": row["dbname"],
            "active": row["id"] == _active_id,
        }
        for row in rows
    ]


def activate_connection(connection_id: int) -> dict:
    global _active, _active_id

    with _meta_engine.connect() as conn:
        row = conn.execute(select(saved_connections).where(saved_connections.c.id == connection_id)).mappings().first()
    if row is None:
        raise DatabaseConnectionError(f"no saved connection with id {connection_id}")

    sqlalchemy_url = decrypt(row["url_encrypted"])
    connection = _build_connection(row["db_type"], sqlalchemy_url, row["dbname"])

    _active = connection
    _active_id = connection_id
    logger.info("activated connection '%s' (id=%s)", row["name"], connection_id)
    return {"id": connection_id, "name": row["name"], "db_type": row["db_type"], "dbname": row["dbname"]}


def delete_connection(connection_id: int) -> None:
    global _active, _active_id

    with _meta_engine.begin() as conn:
        conn.execute(delete(saved_connections).where(saved_connections.c.id == connection_id))

    if _active_id == connection_id:
        _active = None
        _active_id = None
    logger.info("deleted connection id=%s", connection_id)


def _annotation_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "connection_id": row["connection_id"],
        "schema_name": row["schema_name"] or None,
        "table_name": row["table_name"],
        "column_name": row["column_name"] or None,
        "comment": row["comment"],
        "updated_at": row["updated_at"],
    }


def _annotations_map(connection_id: Optional[int]) -> dict[tuple[str, str], str]:
    """(qualified_table_name, column_name) -> comment, column_name='' for a table-level comment.
    Keyed the same way render_schema_text looks things up."""
    if connection_id is None:
        return {}
    with _meta_engine.connect() as conn:
        rows = conn.execute(
            select(
                schema_annotations.c.schema_name,
                schema_annotations.c.table_name,
                schema_annotations.c.column_name,
                schema_annotations.c.comment,
            ).where(schema_annotations.c.connection_id == connection_id)
        ).all()
    return {(_qualify(schema_name or None, table_name), column_name): comment for schema_name, table_name, column_name, comment in rows}


def list_annotations(connection_id: int) -> list[dict]:
    with _meta_engine.connect() as conn:
        rows = conn.execute(
            select(schema_annotations).where(schema_annotations.c.connection_id == connection_id)
        ).mappings().all()
    return [_annotation_row_to_dict(row) for row in rows]


def upsert_annotation(
    connection_id: int,
    table_name: str,
    comment: str,
    schema_name: Optional[str] = None,
    column_name: Optional[str] = None,
) -> dict:
    with _meta_engine.connect() as conn:
        exists = conn.execute(select(saved_connections.c.id).where(saved_connections.c.id == connection_id)).first()
    if exists is None:
        raise DatabaseConnectionError(f"no saved connection with id {connection_id}")

    # best-effort validation: if this connection happens to be the active one, catch a
    # wrong/missing schema_name now — e.g. forgetting schema_name='public' on postgres — instead
    # of silently writing a comment that will never match anything in render_schema_text. Can't
    # validate a connection that isn't currently active, since its live schema isn't loaded.
    if _active is not None and _active_id == connection_id:
        qualified = _qualify(schema_name, table_name)
        table = _active.tables.get(qualified)
        if table is None:
            raise DatabaseConnectionError(
                f"no table '{qualified}' in the active connection's schema — table names are "
                f"schema-qualified for postgres (e.g. schema_name='public', table_name='rental')"
            )
        if column_name and column_name not in {c.name for c in table.columns}:
            raise DatabaseConnectionError(f"no column '{column_name}' on table '{qualified}'")

    values = {
        "connection_id": connection_id,
        "schema_name": schema_name or "",
        "table_name": table_name,
        "column_name": column_name or "",
        "comment": comment,
        "updated_at": datetime.now(timezone.utc),
    }
    stmt = pg_insert(schema_annotations).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["connection_id", "schema_name", "table_name", "column_name"],
        set_={"comment": stmt.excluded.comment, "updated_at": stmt.excluded.updated_at},
    ).returning(schema_annotations)
    with _meta_engine.begin() as conn:
        row = conn.execute(stmt).mappings().first()
    return _annotation_row_to_dict(row)


def delete_annotation(connection_id: int, annotation_id: int) -> None:
    with _meta_engine.begin() as conn:
        result = conn.execute(
            delete(schema_annotations).where(
                schema_annotations.c.id == annotation_id,
                schema_annotations.c.connection_id == connection_id,
            )
        )
    if result.rowcount == 0:
        raise DatabaseConnectionError(f"no annotation with id {annotation_id} for connection {connection_id}")


def get_active() -> Connection:
    if _active is None:
        raise DatabaseConnectionError("no active database connection — save or activate one first")
    return _active


# schemas whose tables are driver/catalog internals, never user data — always skip these
_SYSTEM_SCHEMAS = {"information_schema", "pg_toast"}


def _schemas_to_introspect(engine: Engine, inspector) -> list[Optional[str]]:
    # only postgres nests multiple schemas inside one connected database (mysql's "schema" IS the
    # database, so schema=None already reflects exactly the connected db — no iteration needed)
    if engine.dialect.name != "postgresql":
        return [None]
    schemas = [s for s in inspector.get_schema_names() if s not in _SYSTEM_SCHEMAS and not s.startswith("pg_")]
    return schemas or [None]


def _qualify(schema: Optional[str], table: str) -> str:
    return f"{schema}.{table}" if schema else table


def _introspect(engine: Engine) -> dict[str, TableSchema]:
    inspector = inspect(engine)
    tables: dict[str, TableSchema] = {}

    for schema in _schemas_to_introspect(engine, inspector):
        # bulk reflection: a handful of queries total, not 3-4 per table — matters a lot over a
        # high-latency link, where the old per-table loop meant dozens of extra round trips
        all_columns = inspector.get_multi_columns(schema=schema)
        all_pks = inspector.get_multi_pk_constraint(schema=schema)
        all_fks = inspector.get_multi_foreign_keys(schema=schema)

        for table_key, columns in all_columns.items():
            schema_name, table_name = table_key
            qualified_name = _qualify(schema_name, table_name)
            pk_columns = set(all_pks.get(table_key, {}).get("constrained_columns") or [])

            cols = [ColumnSchema(name=c["name"], type=str(c["type"]), pk=c["name"] in pk_columns) for c in columns]
            fks = [
                ForeignKeySchema(
                    columns=fk["constrained_columns"],
                    referred_table=_qualify(fk.get("referred_schema") or schema_name, fk["referred_table"]),
                    referred_columns=fk["referred_columns"],
                )
                for fk in all_fks.get(table_key, [])
            ]
            tables[qualified_name] = TableSchema(name=qualified_name, columns=cols, foreign_keys=fks)

    return tables


def render_schema_text(tables: dict[str, TableSchema], annotations: dict[tuple[str, str], str]) -> str:
    """Structural data (cached, expensive) + annotations (fresh, cheap) -> the text handed to the
    LLM. A pure function of its inputs so it's cheap to re-run on every request — annotations can
    be edited at any time and show up on the very next call, with no reconnect needed."""
    blocks = []
    for name in sorted(tables):
        table = tables[name]
        table_comment = annotations.get((name, ""))
        lines = [f"Table {name}:" + (f"  -- {table_comment}" if table_comment else "")]
        for col in table.columns:
            marker = " PK" if col.pk else ""
            col_comment = annotations.get((name, col.name))
            suffix = f"  -- {col_comment}" if col_comment else ""
            lines.append(f"  - {col.name} ({col.type}){marker}{suffix}")
        for fk in table.foreign_keys:
            constrained = ", ".join(fk.columns)
            referred = ", ".join(fk.referred_columns)
            lines.append(f"  - FK: {constrained} -> {fk.referred_table}({referred})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def get_active_schema_text() -> str:
    connection = get_active()
    annotations = _annotations_map(_active_id)
    return render_schema_text(connection.tables, annotations)


def run_query(sql: str) -> list[dict]:
    connection = get_active()
    try:
        with connection.engine.connect() as conn:
            if connection.db_type == "postgres":
                conn.exec_driver_sql(f"SET statement_timeout = {QUERY_TIMEOUT_MS}")
            else:
                conn.exec_driver_sql(f"SET SESSION MAX_EXECUTION_TIME = {QUERY_TIMEOUT_MS}")
            result = conn.exec_driver_sql(sql)
            rows = result.fetchmany(MAX_ROWS)
            return [dict(zip(result.keys(), row)) for row in rows]
    except Exception as exc:
        raise SQLExecutionError(str(exc)) from exc
