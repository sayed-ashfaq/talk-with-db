import logging
import re
import unicodedata

import sqlglot
import sqlparse

from app.agents.sql_agent import db
from app.core.exceptions import DestructiveSQLError, UnsafeSQLError

_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)

_FORBIDDEN_KEYWORDS = (
    "CREATE",
    "UPDATE",
    "DELETE",
    "DROP",
    "TRUNCATE",
    "INSERT",
    "ALTER",
    "EXEC",
    "EXECUTE",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_ALLOWED_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def extract_sql(llm_output: str) -> str:
    fences = _FENCE_RE.findall(llm_output)
    if fences:
        return fences[-1].strip()
    return llm_output.strip()


def sanitize(sql: str) -> str:
    sql = unicodedata.normalize("NFKC", sql)
    sql = sql.replace("‘", "'").replace("’", "'")
    sql = sql.replace("“", '"').replace("”", '"')
    sql = sql.replace(" ", " ").replace("​", "")
    return sql.strip().rstrip(";").strip()


def format_sql(sql: str) -> str:
    return sqlparse.format(sql, reindent=True, keyword_case="upper")


def extract_statement(sql: str) -> str:
    statements = [s.strip() for s in sqlparse.split(sql) if s.strip()]
    if not statements:
        raise UnsafeSQLError("no SQL statement found in the model output")
    if len(statements) > 1:
        raise UnsafeSQLError("model output contained multiple SQL statements — only one is allowed")
    return statements[0].rstrip(";").strip()


def transpile(sql: str, dialect: str) -> str:
    try:
        result = sqlglot.transpile(sql, read=dialect, write=dialect, pretty=True)
    except Exception as exc:
        raise UnsafeSQLError(f"sqlglot could not parse the generated SQL: {exc}") from exc
    if not result:
        raise UnsafeSQLError("sqlglot produced no output for the generated SQL")
    return result[0]


def enforce_read_only(sql: str) -> None:
    if not _ALLOWED_START_RE.match(sql):
        raise DestructiveSQLError("only SELECT/WITH statements are allowed")
    match = _FORBIDDEN_RE.search(sql)
    if match:
        raise DestructiveSQLError(f"query contains a blocked write/destructive keyword: {match.group(1).upper()}")


def clean_sql(llm_output: str, dialect: str) -> str:
    sql = extract_sql(llm_output)
    logging.info("Generated SQL query: \n%s", sql)

    sql = sanitize(sql)
    sql = format_sql(sql)
    logging.info("Formatted Fixed SQL query: \n%s", sql)

    sql = extract_statement(sql)
    logging.info("Extracted SQL query: \n%s", sql)

    sql = transpile(sql, dialect)
    logging.info("Transformed SQL query SQLglot: \n%s", sql)

    sql = sanitize(sql)
    enforce_read_only(sql)
    return sql


def clean_and_execute(llm_output: str, dialect: str) -> tuple[str, list[dict]]:
    sql = clean_sql(llm_output, dialect)
    rows = db.run_query(sql)
    return sql, rows
