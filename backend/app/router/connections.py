from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.agents.sql_agent import db, schema_graph
from app.core.logging import get_logger, log_duration

router = APIRouter()
logger = get_logger(__name__)

# graph is expensive to build (embeds every table), so cache it per engine — a fresh engine is
# created on every connect/activate in db.py, so its id() is a natural cache key/invalidator
_graph_cache: dict[int, schema_graph.SchemaGraph] = {}


def _get_or_build_graph(connection: db.Connection) -> schema_graph.SchemaGraph:
    key = id(connection.engine)
    if key not in _graph_cache:
        _graph_cache.clear()  # only the active connection's graph is worth keeping around
        _graph_cache[key] = schema_graph.build_schema_graph(connection.engine)
    return _graph_cache[key]


class SaveConnectionRequest(BaseModel):
    name: str
    db_type: Literal["postgres", "mysql"]
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    dbname: Optional[str] = None
    url: Optional[str] = None

    @model_validator(mode="after")
    def _check_connection_info(self):
        structured = all([self.host, self.port, self.user, self.password, self.dbname])
        if not self.url and not structured:
            raise ValueError("provide either 'url', or all of host/port/user/password/dbname")
        return self


class ConnectionResponse(BaseModel):
    id: int
    name: str
    db_type: str
    dbname: str


class ConnectionSummary(BaseModel):
    id: int
    name: str
    db_type: str
    dbname: str
    active: bool


@router.post("/connections", response_model=ConnectionResponse)
def create_connection(request: SaveConnectionRequest) -> ConnectionResponse:
    logger.info("saving connection '%s' (%s)", request.name, request.db_type)
    result = db.save_connection(
        name=request.name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        dbname=request.dbname,
        url=request.url,
    )
    return ConnectionResponse(**result)


@router.get("/connections", response_model=list[ConnectionSummary])
def get_connections() -> list[ConnectionSummary]:
    return [ConnectionSummary(**row) for row in db.list_connections()]


@router.post("/connections/{connection_id}/activate", response_model=ConnectionResponse)
def activate_connection(connection_id: int) -> ConnectionResponse:
    logger.info("activating connection id=%s", connection_id)
    result = db.activate_connection(connection_id)
    return ConnectionResponse(**result)


@router.delete("/connections/{connection_id}")
def remove_connection(connection_id: int) -> dict:
    db.delete_connection(connection_id)
    return {"deleted": connection_id}


class SchemaResponse(BaseModel):
    schema_type: Literal["plain", "graph"]
    schema_text: str


@router.get("/connections/schema", response_model=SchemaResponse)
def get_schema(schema_type: Literal["plain", "graph"] = "plain") -> SchemaResponse:
    connection = db.get_active()
    if schema_type == "plain":
        text = connection.schema_text
    else:
        with log_duration("Build schema graph (view)"):
            graph = _get_or_build_graph(connection)
        text = schema_graph.render_graph_text(graph)
    return SchemaResponse(schema_type=schema_type, schema_text=text)


class SchemaColumn(BaseModel):
    name: str
    type: str
    pk: bool


class SchemaNode(BaseModel):
    id: str
    columns: list[SchemaColumn]


class SchemaEdge(BaseModel):
    from_: str = Field(alias="from")
    from_column: str
    to: str
    to_column: str

    model_config = {"populate_by_name": True}


class SchemaGraphResponse(BaseModel):
    nodes: list[SchemaNode]
    edges: list[SchemaEdge]


@router.get("/connections/schema-graph", response_model=SchemaGraphResponse, response_model_by_alias=True)
def get_schema_graph() -> SchemaGraphResponse:
    """Structured node-link data for the frontend's schema graph view — same SchemaGraph object
    render_graph_text() flattens to text, just shaped as JSON instead."""
    connection = db.get_active()
    with log_duration("Build schema graph (view)"):
        graph = _get_or_build_graph(connection)

    nodes = [
        SchemaNode(id=name, columns=[SchemaColumn(**c) for c in graph.tables[name].columns])
        for name in graph.table_names
    ]

    seen = set()
    edges = []
    for _, _, data in graph.graph.edges(data=True):
        key = (data["from_table"], data["from_column"], data["to_table"], data["to_column"])
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            SchemaEdge(
                **{
                    "from": data["from_table"],
                    "from_column": data["from_column"],
                    "to": data["to_table"],
                    "to_column": data["to_column"],
                }
            )
        )

    return SchemaGraphResponse(nodes=nodes, edges=edges)
