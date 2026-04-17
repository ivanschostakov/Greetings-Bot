from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.database.schemas.base import ORMSchema

QuestionnaireStatus = Literal["pending_start", "in_progress", "completed", "cancelled"]


class QuestionnaireSessionBase(ORMSchema):
    source_chat_id: int
    source_chat_title: str | None = Field(default=None, max_length=255)
    user_id: int
    delivery_chat_id: int | None = None
    status: QuestionnaireStatus
    question_order: list[int] = Field(min_length=1)
    total_questions: int = Field(ge=1)
    scored_questions_total: int = Field(default=0, ge=0)
    current_question_index: int = Field(default=0, ge=0)
    correct_answers_count: int = Field(default=0, ge=0)
    current_question_id: int | None = None
    active_poll_id: str | None = Field(default=None, max_length=255)
    active_poll_message_id: int | None = None
    completed_at: datetime | None = None


class QuestionnaireSessionCreate(QuestionnaireSessionBase): pass


class QuestionnaireSessionUpdate(ORMSchema):
    source_chat_title: str | None = Field(default=None, max_length=255)
    delivery_chat_id: int | None = None
    status: QuestionnaireStatus | None = None
    question_order: list[int] | None = None
    total_questions: int | None = Field(default=None, ge=1)
    scored_questions_total: int | None = Field(default=None, ge=0)
    current_question_index: int | None = Field(default=None, ge=0)
    correct_answers_count: int | None = Field(default=None, ge=0)
    current_question_id: int | None = None
    active_poll_id: str | None = Field(default=None, max_length=255)
    active_poll_message_id: int | None = None
    completed_at: datetime | None = None


class QuestionnaireSessionRead(QuestionnaireSessionBase):
    id: int
    created_at: datetime
    updated_at: datetime


class QuestionnaireAnswerBase(ORMSchema):
    session_id: int
    question_id: int | None = None
    selected_answer_id: int | None = None
    poll_id: str | None = Field(default=None, max_length=255)
    question_text: str = Field(min_length=1, max_length=255)
    selected_answer_text: str | None = Field(default=None, max_length=255)
    selected_option_index: int | None = Field(default=None, ge=0)
    is_correct: bool | None = None
    was_scored: bool = False


class QuestionnaireAnswerCreate(QuestionnaireAnswerBase): pass


class QuestionnaireAnswerRead(QuestionnaireAnswerBase):
    id: int
    created_at: datetime
    updated_at: datetime
