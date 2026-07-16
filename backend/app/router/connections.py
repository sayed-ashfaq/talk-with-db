from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, model_validator

from app.agents.sql_agent import db
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
