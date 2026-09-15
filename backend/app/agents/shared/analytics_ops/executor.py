"""Runs an AnalyticsPlan against a DataFrame.

The model chooses and parameterizes operations from ops.py's closed vocabulary; this module is the
only thing that ever calls pandas with them, and nothing model-authored is ever executed as code.
Every column name a plan references is checked against the actual DataFrame before anything runs —
an unknown column is a rejected plan, not a pandas KeyError at runtime.
"""

import pandas as pd

from app.agents.shared.analytics_ops.ops import AnalyticsPlan, FilterOp, GroupAggOp, LimitOp, PivotOp, SortOp
from app.core.exceptions import NL2SQLError


class AnalyticsPlanError(NL2SQLError):
    """A plan referenced a column that doesn't exist, or a shape pandas can't execute as given."""


_FILTER_FNS = {
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "gte": lambda s, v: s >= v,
    "lt": lambda s, v: s < v,
    "lte": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v if isinstance(v, list) else [v]),
    "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
}


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise AnalyticsPlanError(f"plan referenced column(s) not in the result: {', '.join(missing)}")


def _apply_filter(df: pd.DataFrame, op: FilterOp) -> pd.DataFrame:
    _require_columns(df, [op.column])
    mask = _FILTER_FNS[op.operator](df[op.column], op.value)
    return df[mask]


def _apply_group_agg(df: pd.DataFrame, op: GroupAggOp) -> pd.DataFrame:
    _require_columns(df, [*op.by, *op.aggregations.keys()])
    grouped = df.groupby(op.by, dropna=False).agg(op.aggregations)
    return grouped.reset_index()


def _apply_sort(df: pd.DataFrame, op: SortOp) -> pd.DataFrame:
    _require_columns(df, op.by)
    return df.sort_values(by=op.by, ascending=op.ascending)


def _apply_pivot(df: pd.DataFrame, op: PivotOp) -> pd.DataFrame:
    _require_columns(df, [op.index, op.columns, op.values])
    pivoted = df.pivot_table(index=op.index, columns=op.columns, values=op.values, aggfunc=op.aggfunc)
    return pivoted.reset_index()


def _apply_limit(df: pd.DataFrame, op: LimitOp) -> pd.DataFrame:
    return df.head(op.n)


_HANDLERS = {
    "filter": _apply_filter,
    "group_agg": _apply_group_agg,
    "sort": _apply_sort,
    "pivot": _apply_pivot,
    "limit": _apply_limit,
}


def apply_plan(df: pd.DataFrame, plan: AnalyticsPlan) -> pd.DataFrame:
    for op in plan.operations:
        df = _HANDLERS[op.op](df, op)
    return df
