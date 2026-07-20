from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, delete, insert, inspect, select
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
class Connection:
    engine: Engine
    db_type: DBType
    dbname: str
    schema_text: str
    tables: dict[str, list[str]]


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

    schema_text, tables = _introspect(engine)
    logger.info("connected to %s database '%s' — %d table(s) found", db_type, dbname, len(tables))
    return Connection(engine=engine, db_type=db_type, dbname=dbname, schema_text=schema_text, tables=tables)


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


def _introspect(engine: Engine) -> tuple[str, dict[str, list[str]]]:
    inspector = inspect(engine)
    tables: dict[str, list[str]] = {}
    entries: dict[str, str] = {}

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
            foreign_keys = all_fks.get(table_key, [])

            lines = [f"Table {qualified_name}:"]
            for col in columns:
                marker = " PK" if col["name"] in pk_columns else ""
                lines.append(f"  - {col['name']} ({col['type']}){marker}")
            for fk in foreign_keys:
                constrained = ", ".join(fk["constrained_columns"])
                referred = ", ".join(fk["referred_columns"])
                referred_name = _qualify(fk.get("referred_schema") or schema_name, fk["referred_table"])
                lines.append(f"  - FK: {constrained} -> {referred_name}({referred})")

            tables[qualified_name] = [col["name"] for col in columns]
            entries[qualified_name] = "\n".join(lines)

    blocks = [entries[name] for name in sorted(entries)]
    return "\n\n".join(blocks), tables


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
