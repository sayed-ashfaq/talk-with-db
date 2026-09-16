"""Runs an AnalyticsPlan against a DataFrame.

The model chooses and parameterizes operations from ops.py's closed vocabulary; this module is the
only thing that ever calls pandas with them, and nothing model-authored is ever executed as code.
Every column name a plan references is checked against the actual DataFrame before anything runs —
an unknown column is a rejected plan, not a pandas KeyError at runtime.
"""

import pandas as pd
from scipy import stats

from app.agents.shared.analytics_ops.ops import (
    AnalyticsPlan,
    CompareOp,
    CorrelateOp,
    DescribeOp,
    FilterOp,
    GroupAggOp,
    LimitOp,
    PivotOp,
    SortOp,
)
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


def _require_columns(df: pd.DataFrame, columns: list[str], op: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        # names the step and what was actually available at that point in the plan (not the
        # original table's columns) — an earlier reshaping step (group_agg above all, which drops
        # every column not named in its own by/aggregations) is the usual reason a column that
        # existed at the start is gone by the time a later step reaches for it
        raise AnalyticsPlanError(
            f"the '{op}' step referenced column(s) not present at that point in the plan: "
            f"{', '.join(missing)} (available then: {', '.join(df.columns)})"
        )


def _apply_filter(df: pd.DataFrame, op: FilterOp) -> pd.DataFrame:
    _require_columns(df, [op.column], "filter")
    mask = _FILTER_FNS[op.operator](df[op.column], op.value)
    return df[mask]


def _apply_group_agg(df: pd.DataFrame, op: GroupAggOp) -> pd.DataFrame:
    _require_columns(df, [*op.by, *op.aggregations.keys()], "group_agg")
    if not op.by:
        # no grouping dimension — a plain aggregate over the whole table (e.g. "what's the total
        # revenue", no GROUP BY equivalent). pandas' groupby([]) rejects this outright ("No group
        # keys passed!"), so it's handled directly rather than routed through groupby at all.
        return pd.DataFrame([df.agg(op.aggregations)])
    grouped = df.groupby(op.by, dropna=False).agg(op.aggregations)
    return grouped.reset_index()


def _apply_sort(df: pd.DataFrame, op: SortOp) -> pd.DataFrame:
    _require_columns(df, op.by, "sort")
    return df.sort_values(by=op.by, ascending=op.ascending)


def _apply_pivot(df: pd.DataFrame, op: PivotOp) -> pd.DataFrame:
    _require_columns(df, [op.index, op.columns, op.values], "pivot")
    pivoted = df.pivot_table(index=op.index, columns=op.columns, values=op.values, aggfunc=op.aggfunc)
    return pivoted.reset_index()


def _apply_limit(df: pd.DataFrame, op: LimitOp) -> pd.DataFrame:
    return df.head(op.n)


def _numeric_columns(df: pd.DataFrame, columns: list[str] | None, op: str) -> list[str]:
    if columns is not None:
        _require_columns(df, columns, op)
        non_numeric = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            raise AnalyticsPlanError(f"not numeric, can't compute statistics on: {', '.join(non_numeric)}")
        return columns
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _apply_describe(df: pd.DataFrame, op: DescribeOp) -> pd.DataFrame:
    columns = _numeric_columns(df, op.columns, "describe")
    if not columns:
        raise AnalyticsPlanError("no numeric columns to describe")

    rows = []
    for name in columns:
        present = df[name].dropna()
        rows.append(
            {
                "column": name,
                "count": int(present.count()),
                "mean": present.mean(),
                "median": present.median(),
                "std": present.std(),
                "min": present.min(),
                "25%": present.quantile(0.25),
                "75%": present.quantile(0.75),
                "max": present.max(),
                "nunique": int(present.nunique()),
                "nulls": int(df[name].isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def _apply_correlate(df: pd.DataFrame, op: CorrelateOp) -> pd.DataFrame:
    columns = _numeric_columns(df, op.columns, "correlate")
    if len(columns) < 2:
        raise AnalyticsPlanError("correlate needs at least two numeric columns")

    corr = df[columns].corr(method=op.method)
    rows = [
        {"column_a": a, "column_b": b, "correlation": corr.loc[a, b]}
        for i, a in enumerate(columns)
        for b in columns[i + 1 :]
    ]
    return pd.DataFrame(rows)


def _apply_compare(df: pd.DataFrame, op: CompareOp) -> pd.DataFrame:
    _require_columns(df, [op.value, op.by], "compare")
    if not pd.api.types.is_numeric_dtype(df[op.value]):
        raise AnalyticsPlanError(f"'{op.value}' is not numeric — compare needs a numeric value column")

    groups = {
        str(name): values
        for name, g in df.groupby(op.by, dropna=True)
        if (values := g[op.value].dropna().to_numpy()).size > 0
    }
    if len(groups) < 2:
        raise AnalyticsPlanError(f"'{op.by}' doesn't have at least two groups with data to compare")

    if len(groups) == 2:
        (_, a), (_, b) = groups.items()
        # Welch's t-test — doesn't assume the two groups have equal variance, the safer default
        # when that's unknown, which it always is here
        statistic, p_value = stats.ttest_ind(a, b, equal_var=False)
        test = "t-test"
    else:
        statistic, p_value = stats.f_oneway(*groups.values())
        test = "ANOVA"

    return pd.DataFrame(
        [
            {
                "group": name,
                "n": len(values),
                "mean": values.mean(),
                "std": values.std(ddof=1) if len(values) > 1 else 0.0,
                "test": test,
                "statistic": statistic,
                "p_value": p_value,
                "significant_at_0.05": bool(p_value < 0.05),
            }
            for name, values in groups.items()
        ]
    )


_HANDLERS = {
    "filter": _apply_filter,
    "group_agg": _apply_group_agg,
    "sort": _apply_sort,
    "pivot": _apply_pivot,
    "limit": _apply_limit,
    "describe": _apply_describe,
    "correlate": _apply_correlate,
    "compare": _apply_compare,
}


def apply_plan(df: pd.DataFrame, plan: AnalyticsPlan) -> pd.DataFrame:
    for op in plan.operations:
        df = _HANDLERS[op.op](df, op)
    return df
