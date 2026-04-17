from datetime import datetime

from pydantic import Field

from src.database.schemas.answer import PollAnswerRead
from src.database.schemas.base import ORMSchema


class PollQuestionBase(ORMSchema):
    chat_id: int
    text: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    right_answer_id: int | None = None


class PollQuestionCreate(PollQuestionBase): pass


class PollQuestionUpdate(ORMSchema):
    text: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    right_answer_id: int | None = None


class PollQuestionRead(PollQuestionBase):
    id: int
    created_at: datetime
    updated_at: datetime


class PollQuestionWithAnswersRead(PollQuestionRead):
    variants: list[PollAnswerRead] = Field(default_factory=list)
    right_answer: PollAnswerRead | None = None
