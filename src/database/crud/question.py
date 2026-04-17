from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import PollQuestion
from src.database.schemas import PollQuestionCreate, PollQuestionUpdate


def _normalize_question_text(text: str) -> str:
    normalized = text.strip()
    if not normalized: raise ValueError("question text must not be empty")
    return normalized


def _normalize_question_description(description: str | None) -> str | None:
    if description is None: return None
    normalized = description.strip()
    return normalized or None


async def create_question(session: AsyncSession, question_in: PollQuestionCreate) -> PollQuestion:
    payload = question_in.model_dump()
    payload["text"] = _normalize_question_text(payload["text"])
    payload["description"] = _normalize_question_description(payload["description"])
    question = PollQuestion(**payload)
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return question


async def get_question(session: AsyncSession, question_id: int) -> PollQuestion | None: return await session.get(PollQuestion, question_id)


async def get_question_with_answers(session: AsyncSession, question_id: int) -> PollQuestion | None:
    result = await session.execute(select(PollQuestion).where(PollQuestion.id == question_id).options(selectinload(PollQuestion.variants), selectinload(PollQuestion.right_answer)))
    return result.scalar_one_or_none()


async def list_chat_questions(session: AsyncSession, chat_id: int) -> list[PollQuestion]:
    result = await session.execute(select(PollQuestion).where(PollQuestion.chat_id == chat_id).order_by(PollQuestion.id))
    return list(result.scalars().all())


async def get_chat_questions_with_answers(session: AsyncSession, chat_id: int) -> list[PollQuestion]:
    result = await session.execute(select(PollQuestion).where(PollQuestion.chat_id == chat_id).options(selectinload(PollQuestion.variants), selectinload(PollQuestion.right_answer)).order_by(PollQuestion.id))
    return list(result.scalars().all())


async def update_question(session: AsyncSession, question: PollQuestion, question_in: PollQuestionUpdate) -> PollQuestion:
    for field, value in question_in.model_dump(exclude_unset=True).items():
        if field == "text" and value is not None: value = _normalize_question_text(value)
        elif field == "description": value = _normalize_question_description(value)
        setattr(question, field, value)
    await session.commit()
    await session.refresh(question)
    return question


async def delete_question(session: AsyncSession, question_id: int) -> bool:
    question = await get_question(session, question_id)
    if question is None: return False
    await session.delete(question)
    await session.commit()
    return True
