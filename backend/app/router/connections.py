from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, model_validator

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
