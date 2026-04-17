from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.answer import PollAnswer
    from src.database.models.chat import ModeratedChat


class PollQuestion(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "poll_questions"

    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("moderated_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    right_answer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("poll_answers.id", name="fk_poll_questions_right_answer_id_poll_answers", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    chat: Mapped["ModeratedChat"] = relationship(back_populates="questions")
    variants: Mapped[list["PollAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan", foreign_keys="PollAnswer.question_id", order_by="PollAnswer.id")
    right_answer: Mapped["PollAnswer | None"] = relationship(foreign_keys=[right_answer_id], post_update=True)
