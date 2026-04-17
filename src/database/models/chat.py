from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import TimestampMixin

if TYPE_CHECKING:
    from src.database.models.question import PollQuestion


class ModeratedChat(Base, TimestampMixin):
    __tablename__ = "moderated_chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=False, nullable=False)
    greetings_text: Mapped[str] = mapped_column(String, nullable=False)
    newcomers_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    questions: Mapped[list["PollQuestion"]] = relationship(back_populates="chat", cascade="all, delete-orphan", passive_deletes=True, order_by="PollQuestion.id")
