from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.question import PollQuestion


class PollAnswer(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "poll_answers"

    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("poll_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped["PollQuestion"] = relationship(back_populates="variants", foreign_keys=[question_id])
