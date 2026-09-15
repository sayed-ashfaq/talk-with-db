"""CSV bytes -> a generic tabular result, capped the same way a live SQL fetch is (see
app.agents.database_agent.sql_agent.db.MAX_ROWS) so an oversized upload can't blow up memory or a
later pandas operation.
"""

import io

import pandas as pd

from app.agents.shared.tabular import QueryResult
from app.core.exceptions import EmptyDocumentError

MAX_ROWS = 5000


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
