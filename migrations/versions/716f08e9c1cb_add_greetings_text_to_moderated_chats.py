"""add greetings text to moderated chats

Revision ID: 716f08e9c1cb
Revises:
Create Date: 2026-04-16 13:57:19.793161
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "716f08e9c1cb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "moderated_chats",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("greetings_text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "poll_questions",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("right_answer_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["moderated_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_poll_questions_chat_id"), "poll_questions", ["chat_id"], unique=False)
    op.create_index(op.f("ix_poll_questions_right_answer_id"), "poll_questions", ["right_answer_id"], unique=False)
    op.create_table(
        "poll_answers",
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.String(length=100), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["poll_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_poll_answers_question_id"), "poll_answers", ["question_id"], unique=False)
    op.create_foreign_key(
        "fk_poll_questions_right_answer_id_poll_answers",
        "poll_questions",
        "poll_answers",
        ["right_answer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "questionnaire_sessions",
        sa.Column("source_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_chat_title", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("question_order", sa.JSON(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("scored_questions_total", sa.Integer(), nullable=False),
        sa.Column("current_question_index", sa.Integer(), nullable=False),
        sa.Column("correct_answers_count", sa.Integer(), nullable=False),
        sa.Column("current_question_id", sa.BigInteger(), nullable=True),
        sa.Column("active_poll_id", sa.String(length=255), nullable=True),
        sa.Column("active_poll_message_id", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_question_id"], ["poll_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_chat_id"], ["moderated_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("active_poll_id"),
    )
    op.create_index(op.f("ix_questionnaire_sessions_source_chat_id"), "questionnaire_sessions", ["source_chat_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_sessions_user_id"), "questionnaire_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_sessions_delivery_chat_id"), "questionnaire_sessions", ["delivery_chat_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_sessions_status"), "questionnaire_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_questionnaire_sessions_current_question_id"), "questionnaire_sessions", ["current_question_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_sessions_active_poll_id"), "questionnaire_sessions", ["active_poll_id"], unique=True)
    op.create_table(
        "questionnaire_answers",
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=True),
        sa.Column("selected_answer_id", sa.BigInteger(), nullable=True),
        sa.Column("poll_id", sa.String(length=255), nullable=True),
        sa.Column("question_text", sa.String(length=255), nullable=False),
        sa.Column("selected_answer_text", sa.String(length=255), nullable=True),
        sa.Column("selected_option_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("was_scored", sa.Boolean(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["poll_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["selected_answer_id"], ["poll_answers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["questionnaire_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "question_id", name="uq_questionnaire_answers_session_question"),
    )
    op.create_index(op.f("ix_questionnaire_answers_session_id"), "questionnaire_answers", ["session_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_answers_question_id"), "questionnaire_answers", ["question_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_answers_selected_answer_id"), "questionnaire_answers", ["selected_answer_id"], unique=False)
    op.create_index(op.f("ix_questionnaire_answers_poll_id"), "questionnaire_answers", ["poll_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_questionnaire_answers_poll_id"), table_name="questionnaire_answers")
    op.drop_index(op.f("ix_questionnaire_answers_selected_answer_id"), table_name="questionnaire_answers")
    op.drop_index(op.f("ix_questionnaire_answers_question_id"), table_name="questionnaire_answers")
    op.drop_index(op.f("ix_questionnaire_answers_session_id"), table_name="questionnaire_answers")
    op.drop_table("questionnaire_answers")
    op.drop_index(op.f("ix_questionnaire_sessions_active_poll_id"), table_name="questionnaire_sessions")
    op.drop_index(op.f("ix_questionnaire_sessions_current_question_id"), table_name="questionnaire_sessions")
    op.drop_index(op.f("ix_questionnaire_sessions_status"), table_name="questionnaire_sessions")
    op.drop_index(op.f("ix_questionnaire_sessions_delivery_chat_id"), table_name="questionnaire_sessions")
    op.drop_index(op.f("ix_questionnaire_sessions_user_id"), table_name="questionnaire_sessions")
    op.drop_index(op.f("ix_questionnaire_sessions_source_chat_id"), table_name="questionnaire_sessions")
    op.drop_table("questionnaire_sessions")
    op.drop_constraint("fk_poll_questions_right_answer_id_poll_answers", "poll_questions", type_="foreignkey")
    op.drop_index(op.f("ix_poll_answers_question_id"), table_name="poll_answers")
    op.drop_table("poll_answers")
    op.drop_index(op.f("ix_poll_questions_right_answer_id"), table_name="poll_questions")
    op.drop_index(op.f("ix_poll_questions_chat_id"), table_name="poll_questions")
    op.drop_table("poll_questions")
    op.drop_table("moderated_chats")
