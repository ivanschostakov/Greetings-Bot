"""add newcomers thread id to moderated chats

Revision ID: b3326d829e4a
Revises: 716f08e9c1cb
Create Date: 2026-04-16 16:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3326d829e4a"
down_revision: Union[str, Sequence[str], None] = "716f08e9c1cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("moderated_chats", sa.Column("newcomers_thread_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("moderated_chats", "newcomers_thread_id")
