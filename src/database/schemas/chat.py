from datetime import datetime

from pydantic import Field

from src.database.schemas.base import ORMSchema
from src.database.schemas.question import PollQuestionRead, PollQuestionWithAnswersRead


class ModeratedChatBase(ORMSchema):
    id: int
    greetings_text: str = Field(min_length=1)
    newcomers_thread_id: int | None = None


class ModeratedChatCreate(ModeratedChatBase): pass


class ModeratedChatUpdate(ORMSchema):
    greetings_text: str | None = Field(default=None, min_length=1)
    newcomers_thread_id: int | None = None


class ModeratedChatRead(ModeratedChatBase):
    created_at: datetime
    updated_at: datetime


class ModeratedChatWithQuestionsRead(ModeratedChatRead):
    questions: list[PollQuestionRead] = Field(default_factory=list)


class ModeratedChatWithQuestionsAndAnswersRead(ModeratedChatRead):
    questions: list[PollQuestionWithAnswersRead] = Field(default_factory=list)
