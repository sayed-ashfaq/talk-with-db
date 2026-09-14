"""chats section

Revision ID: 5a084928443c
Revises: 65782ea3b537
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a084928443c'
down_revision: Union[str, Sequence[str], None] = '65782ea3b537'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills every existing chat as "database" — the only section that existed
    # before this column did, so that's a no-behavior-change migration for current users.
    op.add_column(
        "chats", sa.Column("section", sa.String(length=16), nullable=False, server_default="database")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chats", "section")
