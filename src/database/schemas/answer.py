from datetime import datetime

from pydantic import Field

from src.database.schemas.base import ORMSchema


class PollAnswerBase(ORMSchema):
    question_id: int
    text: str = Field(min_length=1, max_length=100)


class PollAnswerCreate(PollAnswerBase): pass


class PollAnswerUpdate(ORMSchema):
    text: str | None = Field(default=None, min_length=1, max_length=100)


class PollAnswerRead(PollAnswerBase):
    id: int
    created_at: datetime
    updated_at: datetime
