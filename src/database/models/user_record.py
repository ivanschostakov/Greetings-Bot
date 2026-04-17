from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin


class UserRecord(Base, IdPkMixin):
    __tablename__ = "user_records"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("moderated_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
