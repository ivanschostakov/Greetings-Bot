from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.answer import PollAnswer
    from src.database.models.question import PollQuestion


class QuestionnaireSession(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "questionnaire_sessions"

    source_chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("moderated_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    source_chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    delivery_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    question_order: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_questions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_answers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_question_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("poll_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    active_poll_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    active_poll_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers: Mapped[list["QuestionnaireAnswer"]] = relationship(back_populates="session", cascade="all, delete-orphan", passive_deletes=True, order_by="QuestionnaireAnswer.id")
    current_question: Mapped["PollQuestion | None"] = relationship(foreign_keys=[current_question_id])


class QuestionnaireAnswer(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "questionnaire_answers"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_questionnaire_answers_session_question"),)

    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("poll_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    selected_answer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("poll_answers.id", ondelete="SET NULL"), nullable=True, index=True)
    poll_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    question_text: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_answer_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    was_scored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    session: Mapped["QuestionnaireSession"] = relationship(back_populates="answers", foreign_keys=[session_id])
    question: Mapped["PollQuestion | None"] = relationship(foreign_keys=[question_id])
    selected_answer: Mapped["PollAnswer | None"] = relationship(foreign_keys=[selected_answer_id])
