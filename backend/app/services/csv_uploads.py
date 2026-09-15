"""Persistence for CSV uploads — chat-scoped only, no library concept (see the Phase 2 design
decision). Scoped like everything else here: every function takes the signed-in user and filters on
their id.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.tabular import QueryResult
from app.db.models import CsvUpload


async def create_csv_upload(
    session: AsyncSession, user_id: uuid.UUID, chat_id: uuid.UUID, filename: str, result: QueryResult
) -> CsvUpload:
    upload = CsvUpload(
        user_id=user_id,
        chat_id=chat_id,
        filename=filename,
        columns=result.columns,
        rows=result.rows,
        truncated=result.truncated,
    )
    session.add(upload)
    await session.commit()
    await session.refresh(upload)
    return upload


async def load_latest(session: AsyncSession, chat_id: uuid.UUID) -> Optional[QueryResult]:
    """This chat's most recent upload, read back by the router before the graph runs — the graph is
    synchronous and can't await this itself, same reason prior_result is resolved there too."""
    upload = await session.scalar(
        select(CsvUpload).where(CsvUpload.chat_id == chat_id).order_by(CsvUpload.created_at.desc()).limit(1)
    )
    if upload is None:
        return None
    return QueryResult(columns=upload.columns, rows=upload.rows, truncated=upload.truncated)
