from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import QuestionnaireAnswer, QuestionnaireSession
from src.database.schemas import QuestionnaireAnswerCreate, QuestionnaireSessionCreate, QuestionnaireSessionUpdate

OPEN_QUESTIONNAIRE_STATUSES = ("pending_start", "in_progress")


async def create_questionnaire_session(session: AsyncSession, questionnaire_in: QuestionnaireSessionCreate) -> QuestionnaireSession:
    questionnaire = QuestionnaireSession(**questionnaire_in.model_dump())
    session.add(questionnaire)
    await session.commit()
    await session.refresh(questionnaire)
    return questionnaire


async def get_questionnaire_session(session: AsyncSession, questionnaire_id: int) -> QuestionnaireSession | None: return await session.get(QuestionnaireSession, questionnaire_id)


async def get_questionnaire_session_for_user(session: AsyncSession, questionnaire_id: int, user_id: int) -> QuestionnaireSession | None:
    result = await session.execute(select(QuestionnaireSession).where(QuestionnaireSession.id == questionnaire_id, QuestionnaireSession.user_id == user_id))
    return result.scalar_one_or_none()


async def get_active_questionnaire_by_poll_id(session: AsyncSession, poll_id: str) -> QuestionnaireSession | None:
    result = await session.execute(select(QuestionnaireSession).where(QuestionnaireSession.active_poll_id == poll_id))
    return result.scalar_one_or_none()


async def get_latest_resumable_questionnaire_for_user(session: AsyncSession, user_id: int) -> QuestionnaireSession | None:
    result = await session.execute(
        select(QuestionnaireSession).where(
            QuestionnaireSession.user_id == user_id, QuestionnaireSession.status.in_(OPEN_QUESTIONNAIRE_STATUSES)
        ).order_by(QuestionnaireSession.updated_at.desc())
    )
    return result.scalars().first()


async def list_open_questionnaires_for_user_and_chat(session: AsyncSession, source_chat_id: int, user_id: int) -> list[QuestionnaireSession]:
    result = await session.execute(
        select(QuestionnaireSession).where(
            QuestionnaireSession.source_chat_id == source_chat_id,
            QuestionnaireSession.user_id == user_id,
            QuestionnaireSession.status.in_(OPEN_QUESTIONNAIRE_STATUSES),
        ).order_by(QuestionnaireSession.created_at.desc())
    )
    return list(result.scalars().all())


async def get_questionnaire_answer_for_session_and_question(session: AsyncSession, questionnaire_id: int, question_id: int) -> QuestionnaireAnswer | None:
    result = await session.execute(select(QuestionnaireAnswer).where(QuestionnaireAnswer.session_id == questionnaire_id, QuestionnaireAnswer.question_id == question_id))
    return result.scalar_one_or_none()


async def update_questionnaire_session(session: AsyncSession, questionnaire: QuestionnaireSession, questionnaire_in: QuestionnaireSessionUpdate) -> QuestionnaireSession:
    for field, value in questionnaire_in.model_dump(exclude_unset=True).items(): setattr(questionnaire, field, value)
    await session.commit()
    await session.refresh(questionnaire)
    return questionnaire


async def cancel_open_questionnaires_for_user_and_chat(session: AsyncSession, source_chat_id: int, user_id: int) -> list[QuestionnaireSession]:
    questionnaires = await list_open_questionnaires_for_user_and_chat(session=session, source_chat_id=source_chat_id, user_id=user_id)
    if not questionnaires: return []
    for questionnaire in questionnaires:
        questionnaire.status = "cancelled"
        questionnaire.active_poll_id = None
        questionnaire.active_poll_message_id = None
        questionnaire.current_question_id = None
    await session.commit()
    for questionnaire in questionnaires: await session.refresh(questionnaire)
    return questionnaires


async def complete_questionnaire_session(session: AsyncSession, questionnaire: QuestionnaireSession) -> QuestionnaireSession:
    questionnaire.status = "completed"
    questionnaire.active_poll_id = None
    questionnaire.active_poll_message_id = None
    questionnaire.current_question_id = None
    questionnaire.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(questionnaire)
    return questionnaire


async def create_questionnaire_answer(session: AsyncSession, answer_in: QuestionnaireAnswerCreate) -> QuestionnaireAnswer:
    answer = QuestionnaireAnswer(**answer_in.model_dump())
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


async def delete_questionnaire_session(session: AsyncSession, questionnaire: QuestionnaireSession) -> None:
    await session.delete(questionnaire)
    await session.commit()
