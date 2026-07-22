import asyncio
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.agents.sql_agent import db, schema_graph
from app.core.logging import get_logger, log_duration
from app.db.session import SessionDep
from app.services import connections as connection_service

router = APIRouter()
logger = get_logger(__name__)

# graph is expensive to build (embeds every table), so cache it per engine — a fresh engine is
# created on every connect/activate in db.py, so its id() is a natural cache key/invalidator
_graph_cache: dict[int, schema_graph.SchemaGraph] = {}


async def _get_or_build_graph(connection: db.Connection) -> schema_graph.SchemaGraph:
    key = id(connection.engine)
    if key not in _graph_cache:
        _graph_cache.clear()  # only the active connection's graph is worth keeping around
        with log_duration("Build schema graph (view)"):
            # embeds every table name — seconds of CPU and blocking driver calls, so off-thread
            _graph_cache[key] = await asyncio.to_thread(schema_graph.build_schema_graph, connection.engine)
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
    id: uuid.UUID
    name: str
    db_type: str
    dbname: str


class ConnectionSummary(BaseModel):
    id: uuid.UUID
    name: str
    db_type: str
    dbname: str
    active: bool


@router.post("/connections", response_model=ConnectionResponse)
async def create_connection(request: SaveConnectionRequest, session: SessionDep) -> ConnectionResponse:
    logger.info("saving connection '%s' (%s)", request.name, request.db_type)
    result = await connection_service.save_connection(
        session,
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
async def get_connections(session: SessionDep) -> list[ConnectionSummary]:
    return [ConnectionSummary(**row) for row in await connection_service.list_connections(session)]


@router.post("/connections/{connection_id}/activate", response_model=ConnectionResponse)
async def activate_connection(connection_id: uuid.UUID, session: SessionDep) -> ConnectionResponse:
    logger.info("activating connection id=%s", connection_id)
    result = await connection_service.activate_connection(session, connection_id)
    return ConnectionResponse(**result)


@router.delete("/connections/{connection_id}")
async def remove_connection(connection_id: uuid.UUID, session: SessionDep) -> dict:
    await connection_service.delete_connection(session, connection_id)
    return {"deleted": str(connection_id)}


class AnnotationRequest(BaseModel):
    table_name: str
    comment: str
    schema_name: Optional[str] = None
    column_name: Optional[str] = None  # omit/None for a table-level comment


class AnnotationResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    table_name: str
    comment: str
    schema_name: Optional[str] = None
    column_name: Optional[str] = None
    updated_at: datetime


@router.get("/connections/{connection_id}/annotations", response_model=list[AnnotationResponse])
async def get_annotations(connection_id: uuid.UUID, session: SessionDep) -> list[AnnotationResponse]:
    return [AnnotationResponse(**row) for row in await connection_service.list_annotations(session, connection_id)]


@router.put("/connections/{connection_id}/annotations", response_model=AnnotationResponse)
async def put_annotation(
    connection_id: uuid.UUID, request: AnnotationRequest, session: SessionDep
) -> AnnotationResponse:
    result = await connection_service.upsert_annotation(
        session,
        connection_id=connection_id,
        table_name=request.table_name,
        comment=request.comment,
        schema_name=request.schema_name,
        column_name=request.column_name,
    )
    return AnnotationResponse(**result)


@router.delete("/connections/{connection_id}/annotations/{annotation_id}")
async def remove_annotation(connection_id: uuid.UUID, annotation_id: uuid.UUID, session: SessionDep) -> dict:
    await connection_service.delete_annotation(session, connection_id, annotation_id)
    return {"deleted": str(annotation_id)}


class SchemaResponse(BaseModel):
    schema_type: Literal["plain", "graph"]
    schema_text: str


@router.get("/connections/schema", response_model=SchemaResponse)
async def get_schema(session: SessionDep, schema_type: Literal["plain", "graph"] = "plain") -> SchemaResponse:
    connection = db.get_active()
    if schema_type == "plain":
        text = await connection_service.get_active_schema_text(session)
    else:
        graph = await _get_or_build_graph(connection)
        text = schema_graph.render_graph_text(graph)
    return SchemaResponse(schema_type=schema_type, schema_text=text)


class SchemaColumn(BaseModel):
    name: str
    type: str
    pk: bool


class SchemaNode(BaseModel):
    id: str
    columns: list[SchemaColumn]
    table_schema: Optional[str] = None
    row_count: int = 0


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
async def get_schema_graph() -> SchemaGraphResponse:
    """Structured node-link data for the frontend's schema graph view — same SchemaGraph object
    render_graph_text() flattens to text, just shaped as JSON instead."""
    connection = db.get_active()
    graph = await _get_or_build_graph(connection)
    row_counts = await asyncio.to_thread(schema_graph.get_row_counts, connection.engine)

    nodes = [
        SchemaNode(
            id=name,
            columns=[SchemaColumn(**c) for c in graph.tables[name].columns],
            table_schema=name.rsplit(".", 1)[0] if "." in name else None,
            row_count=row_counts.get(name, 0),
        )
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
