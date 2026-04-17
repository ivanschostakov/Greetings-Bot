from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PollAnswer
from src.database.schemas import PollAnswerCreate, PollAnswerUpdate


def _normalize_answer_text(text: str) -> str:
    normalized = text.strip()
    if not normalized: raise ValueError("answer text must not be empty")
    return normalized


async def create_answer(session: AsyncSession, answer_in: PollAnswerCreate) -> PollAnswer:
    payload = answer_in.model_dump()
    payload["text"] = _normalize_answer_text(payload["text"])
    answer = PollAnswer(**payload)
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


async def get_answer(session: AsyncSession, answer_id: int) -> PollAnswer | None: return await session.get(PollAnswer, answer_id)


async def list_question_answers(session: AsyncSession, question_id: int) -> list[PollAnswer]:
    result = await session.execute(select(PollAnswer).where(PollAnswer.question_id == question_id).order_by(PollAnswer.id))
    return list(result.scalars().all())


async def update_answer(session: AsyncSession, answer: PollAnswer, answer_in: PollAnswerUpdate) -> PollAnswer:
    for field, value in answer_in.model_dump(exclude_unset=True).items():
        if field == "text" and value is not None: value = _normalize_answer_text(value)
        setattr(answer, field, value)
    await session.commit()
    await session.refresh(answer)
    return answer


async def delete_answer(session: AsyncSession, answer_id: int) -> bool:
    answer = await get_answer(session, answer_id)
    if answer is None: return False
    await session.delete(answer)
    await session.commit()
    return True
