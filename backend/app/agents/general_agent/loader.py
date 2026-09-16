"""CSV bytes -> a generic tabular result, capped well above database_agent.sql_agent.db.MAX_ROWS —
an upload is a one-time, user-controlled file rather than a live query against someone else's
database, so it can afford a much higher ceiling before an oversized file risks blowing up memory or
a later pandas/scipy operation.
"""

import io

import pandas as pd

from app.agents.shared.tabular import QueryResult
from app.core.exceptions import EmptyDocumentError

MAX_ROWS = 100_000


def parse_csv(csv_bytes: bytes) -> QueryResult:
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except pd.errors.EmptyDataError as exc:
        # pandas raises this itself for a file with no columns at all (e.g. truly empty), rather
        # than returning an empty frame — df.empty below only catches headers-with-no-rows
        raise EmptyDocumentError from exc

    if df.empty:
        raise EmptyDocumentError

    truncated = len(df) > MAX_ROWS
    df = df.head(MAX_ROWS)
    return QueryResult(
        columns=[str(c) for c in df.columns],
        rows=df.to_dict(orient="records"),
        truncated=truncated,
    )
