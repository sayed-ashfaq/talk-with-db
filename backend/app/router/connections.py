from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.sql_agent import db
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ConnectRequest(BaseModel):
    db_type: Literal["postgres", "mysql"]
    host: str
    port: int
    user: str
    password: str
    dbname: str


class ConnectResponse(BaseModel):
    connected: bool
    db_type: str
    dbname: str
    tables: list[str]


@router.post("/connect", response_model=ConnectResponse)
def connect(request: ConnectRequest) -> ConnectResponse:
    logger.info(
        "connect request: %s db '%s' at %s:%s", request.db_type, request.dbname, request.host, request.port
    )
    connection = db.connect(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        dbname=request.dbname,
    )
    return ConnectResponse(
        connected=True,
        db_type=connection.db_type,
        dbname=connection.dbname,
        tables=list(connection.tables.keys()),
    )
