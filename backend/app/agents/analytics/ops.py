"""The declarative operations an analytics plan may contain — a fixed, closed vocabulary the model
picks from and parameterizes, not code it writes.

Same precedent as visualizer/charts.py: the model's job is choosing and parameterizing from a
validated set of shapes; app.agents.analytics.executor is the only thing that ever turns one into an
actual pandas call.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

AggFunc = Literal["sum", "mean", "count", "min", "max", "median", "nunique"]
FilterOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"]


class FilterOp(BaseModel):
    # no default on `op` anywhere below: a discriminated union needs the discriminator field
    # required in the generated JSON schema, or a model that omits it (defaults make that legal)
    # leaves every subschema matching at once — confirmed live against Groq, which 400'd with
    # "'oneOf' failed, subschemas 1, 2 matched" the moment `op` carried a default.
    op: Literal["filter"]
    column: str
    operator: FilterOperator
    value: object


class GroupAggOp(BaseModel):
    op: Literal["group_agg"]
    by: list[str]
    aggregations: dict[str, AggFunc] = Field(description="column name -> aggregation function")


class SortOp(BaseModel):
    op: Literal["sort"]
    by: list[str]
    ascending: bool = True


class PivotOp(BaseModel):
    op: Literal["pivot"]
    index: str
    columns: str
    values: str
    aggfunc: Literal["sum", "mean", "count"] = "sum"


class LimitOp(BaseModel):
    op: Literal["limit"]
    n: int


Operation = Annotated[
    Union[FilterOp, GroupAggOp, SortOp, PivotOp, LimitOp],
    Field(discriminator="op"),
]


class AnalyticsPlan(BaseModel):
    operations: list[Operation]
    explanation: str = Field(description="one sentence on what the final result represents, for whoever writes the answer from it")
