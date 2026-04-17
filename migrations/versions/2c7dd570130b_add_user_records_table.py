"""add user records table

Revision ID: 2c7dd570130b
Revises: b3326d829e4a
Create Date: 2026-04-17 16:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2c7dd570130b"
down_revision: Union[str, Sequence[str], None] = "b3326d829e4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_records",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["moderated_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_records_user_id"), "user_records", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_records_chat_id"), "user_records", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_records_chat_id"), table_name="user_records")
    op.drop_index(op.f("ix_user_records_user_id"), table_name="user_records")
    op.drop_table("user_records")
