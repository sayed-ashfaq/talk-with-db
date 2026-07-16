from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

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


def connect(db_type: DBType, host: str, port: int, user: str, password: str, dbname: str) -> Connection:
    global _active

    url = f"{_DRIVER[db_type]}://{user}:{password}@{host}:{port}/{dbname}"
    logger.info("connecting to %s database '%s' at %s:%s", db_type, dbname, host, port)
    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:
        raise DatabaseConnectionError(
            f"could not connect to {db_type} database '{dbname}' at {host}:{port}"
        ) from exc

    schema_text, tables = _introspect(engine)
    _active = Connection(engine=engine, db_type=db_type, dbname=dbname, schema_text=schema_text, tables=tables)
    logger.info("connected — %d table(s) found", len(tables))
    return _active


def get_active() -> Connection:
    if _active is None:
        raise DatabaseConnectionError("no active database connection — call /connect first")
    return _active


def _introspect(engine: Engine) -> tuple[str, dict[str, list[str]]]:
    inspector = inspect(engine)
    tables: dict[str, list[str]] = {}
    blocks: list[str] = []

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
        foreign_keys = inspector.get_foreign_keys(table_name)

        lines = [f"Table {table_name}:"]
        for col in columns:
            marker = " PK" if col["name"] in pk_columns else ""
            lines.append(f"  - {col['name']} ({col['type']}){marker}")
        for fk in foreign_keys:
            constrained = ", ".join(fk["constrained_columns"])
            referred = ", ".join(fk["referred_columns"])
            lines.append(f"  - FK: {constrained} -> {fk['referred_table']}({referred})")

        tables[table_name] = [col["name"] for col in columns]
        blocks.append("\n".join(lines))

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
