"""A generic tabular result — rows + columns + a truncation flag — with no assumption about where
the rows came from. sql_agent's run_query produces one from a live query, but analytics_ops,
visualizer, and analytics_agent all consume this shape regardless of source, so it lives here rather than
under sql_agent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResult:
    """One result set's output.

    Columns are carried separately from rows because an empty result still has a shape: a table
    with headers and no data renders, whereas an empty list of dicts is indistinguishable from
    having nothing to show.
    """

    columns: list[str]
    rows: list[dict]
    # we hit MAX_ROWS and there may be more behind it. False positive in exactly one case — a
    # result that happens to be MAX_ROWS rows long — which costs the user a truthful "capped at
    # 5000 rows" note and nothing else.
    truncated: bool

    @property
    def row_count(self) -> int:
        return len(self.rows)
