import asyncio

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from logging import getLogger
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import PollAnswer
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.helpers.configuration import NEWCOMER_RESTRICTION_MINUTES
from src.bot.helpers.questionnaire import build_completion_message, build_feedback_message, build_group_completion_greeting, build_group_timeout_greeting, build_private_intro, build_question_order, build_question_text, build_questionnaire_payload, build_restart_keyboard, prepare_question
from src.database import get_session
from src.database.crud import cancel_open_questionnaires_for_user_and_chat, complete_questionnaire_session, create_questionnaire_answer, create_questionnaire_session, create_user_record, delete_questionnaire_session, get_active_questionnaire_by_poll_id, get_chat_with_questions_and_answers, get_latest_resumable_questionnaire_for_user as get_latest_resumable_questionnaire_crud, get_question_with_answers, get_questionnaire_answer_for_session_and_question, get_questionnaire_session, get_questionnaire_session_for_user, list_open_questionnaires_for_user_and_chat, update_questionnaire_session
from src.database.models import ModeratedChat, PollQuestion, QuestionnaireSession
from src.database.schemas import QuestionnaireAnswerCreate, QuestionnaireSessionCreate, QuestionnaireSessionUpdate, UserRecordCreate

logger = getLogger(__name__)


@dataclass(slots=True)
class TrackedQuestionnaireMessages:
    chat_id: int
    expires_at: datetime
    user_mention_html: str | None = None
    message_ids: set[int] = field(default_factory=set)


TRACKED_MESSAGE_TTL = timedelta(minutes=NEWCOMER_RESTRICTION_MINUTES)
ENDING_MESSAGE_TTL = timedelta(seconds=30)
_tracked_questionnaire_messages: dict[int, TrackedQuestionnaireMessages] = {}
_questionnaire_cleanup_tasks: dict[int, asyncio.Task[None]] = {}


def _thread_kwargs(thread_id: int | None) -> dict[str, int]:
    if thread_id is None: return {}
    return {"message_thread_id": thread_id}


def _completion_reply_markup(questionnaire: QuestionnaireSession):
    if questionnaire.delivery_chat_id == questionnaire.source_chat_id: return None
    return build_restart_keyboard(questionnaire.source_chat_id)


def _is_group_delivery(questionnaire: QuestionnaireSession) -> bool: return questionnaire.delivery_chat_id is not None and questionnaire.delivery_chat_id == questionnaire.source_chat_id
async def _resolve_delivery_thread_id(session: AsyncSession, questionnaire: QuestionnaireSession) -> int | None:
    if not _is_group_delivery(questionnaire): return None
    chat = await session.get(ModeratedChat, questionnaire.source_chat_id)
    if chat is None: return None
    return chat.newcomers_thread_id


def track_questionnaire_message(
    questionnaire_id: int,
    chat_id: int,
    message_id: int | None,
    *,
    now: datetime | None = None,
    user_mention_html: str | None = None,
) -> bool:
    current_time = now or datetime.now(UTC)
    tracked = _tracked_questionnaire_messages.get(questionnaire_id)
    if tracked is None:
        tracked = TrackedQuestionnaireMessages(chat_id=chat_id, expires_at=current_time + TRACKED_MESSAGE_TTL, user_mention_html=user_mention_html)
        _tracked_questionnaire_messages[questionnaire_id] = tracked
    if tracked.chat_id != chat_id: return False
    if tracked.expires_at <= current_time:
        _tracked_questionnaire_messages.pop(questionnaire_id, None)
        return False
    if user_mention_html is not None: tracked.user_mention_html = user_mention_html
    if message_id is not None:
        tracked.message_ids.add(message_id)
    return True


def _drop_tracked_questionnaire_messages(questionnaire_id: int) -> None: _tracked_questionnaire_messages.pop(questionnaire_id, None)
async def _delete_tracked_questionnaire_messages(bot: Bot, questionnaire_id: int) -> TrackedQuestionnaireMessages | None:
    tracked = _tracked_questionnaire_messages.pop(questionnaire_id, None)
    if tracked is None: return None
    for message_id in sorted(tracked.message_ids, reverse=True):
        try: await bot.delete_message(tracked.chat_id, message_id)
        except (TelegramBadRequest, TelegramForbiddenError): logger.debug("Unable to delete tracked onboarding message %s in chat %s", message_id, tracked.chat_id)
    return tracked


def _build_poll_description(questionnaire_id: int) -> str | None:
    tracked = _tracked_questionnaire_messages.get(questionnaire_id)
    if tracked is None or tracked.expires_at <= datetime.now(UTC):
        _tracked_questionnaire_messages.pop(questionnaire_id, None)
        return None
    if tracked.user_mention_html is None: return None
    return f"Для {tracked.user_mention_html}"


def _cancel_questionnaire_cleanup_task(questionnaire_id: int) -> None:
    task = _questionnaire_cleanup_tasks.pop(questionnaire_id, None)
    if task is not None and not task.done(): task.cancel()


async def _delete_message_after_delay(bot: Bot, chat_id: int, message_id: int, delay: timedelta) -> None:
    try:
        await asyncio.sleep(delay.total_seconds())
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.debug("Unable to delete delayed message %s in chat %s", message_id, chat_id)


def _schedule_ending_message_cleanup(bot: Bot, chat_id: int, message_id: int) -> None:
    asyncio.create_task(_delete_message_after_delay(bot, chat_id, message_id, ENDING_MESSAGE_TTL))


async def _questionnaire_cleanup_worker(bot: Bot, questionnaire_id: int) -> None:
    try:
        await asyncio.sleep(TRACKED_MESSAGE_TTL.total_seconds())
        async with get_session() as session:
            questionnaire = await get_questionnaire_session(session, questionnaire_id)
            if questionnaire is None or questionnaire.status in {"completed", "cancelled"}:
                return
            if questionnaire.status == "pending_start":
                await delete_questionnaire_session(session, questionnaire)
                await _delete_tracked_questionnaire_messages(bot, questionnaire_id)
                return
            if not _is_group_delivery(questionnaire):
                return
            delivery_chat_id = questionnaire.delivery_chat_id
            delivery_thread_id = await _resolve_delivery_thread_id(session, questionnaire)
            await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(status="cancelled", current_question_id=None, active_poll_id=None, active_poll_message_id=None))
        tracked = await _delete_tracked_questionnaire_messages(bot, questionnaire_id)
        if delivery_chat_id is None: return
        timeout_message = await bot.send_message(
            delivery_chat_id,
            build_group_timeout_greeting(tracked.user_mention_html if tracked is not None else None),
            parse_mode=ParseMode.HTML,
            **_thread_kwargs(delivery_thread_id),
        )
        _schedule_ending_message_cleanup(bot, delivery_chat_id, timeout_message.message_id)
        async with get_session() as session:
            questionnaire = await get_questionnaire_session(session, questionnaire_id)
            if questionnaire is not None: await delete_questionnaire_session(session, questionnaire)
    except asyncio.CancelledError: raise
    finally:
        current_task = _questionnaire_cleanup_tasks.get(questionnaire_id)
        if current_task is asyncio.current_task(): _questionnaire_cleanup_tasks.pop(questionnaire_id, None)


def schedule_questionnaire_cleanup(bot: Bot, questionnaire_id: int) -> None:
    _cancel_questionnaire_cleanup_task(questionnaire_id)
    _questionnaire_cleanup_tasks[questionnaire_id] = asyncio.create_task(_questionnaire_cleanup_worker(bot, questionnaire_id))


async def consume_questionnaire_link(bot: Bot, questionnaire_id: int) -> None:
    _cancel_questionnaire_cleanup_task(questionnaire_id)
    await _delete_tracked_questionnaire_messages(bot, questionnaire_id)


async def get_moderated_chat(chat_id: int) -> ModeratedChat | None:
    async with get_session() as session: return await get_chat_with_questions_and_answers(session, chat_id)


async def get_latest_resumable_questionnaire(user_id: int) -> QuestionnaireSession | None:
    async with get_session() as session: return await get_latest_resumable_questionnaire_crud(session, user_id)


async def build_questionnaire_start_link(bot: Bot, questionnaire_id: int) -> str: return await create_start_link(bot, build_questionnaire_payload(questionnaire_id))


async def stop_poll(bot: Bot, chat_id: int | None, message_id: int | None) -> None:
    if chat_id is None or message_id is None: return
    try: await bot.stop_poll(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramForbiddenError): logger.debug("Unable to stop poll chat_id=%s message_id=%s", chat_id, message_id)


async def _close_open_questionnaires(bot: Bot, source_chat_id: int, user_id: int) -> None:
    async with get_session() as session:
        questionnaires = await list_open_questionnaires_for_user_and_chat(session, source_chat_id, user_id)
        polls_to_stop = [(item.delivery_chat_id, item.active_poll_message_id) for item in questionnaires]
        await cancel_open_questionnaires_for_user_and_chat(session, source_chat_id, user_id)
    for questionnaire in questionnaires:
        _cancel_questionnaire_cleanup_task(questionnaire.id)
        _drop_tracked_questionnaire_messages(questionnaire.id)
    for chat_id, message_id in polls_to_stop: await stop_poll(bot, chat_id, message_id)


async def create_pending_questionnaire(bot: Bot, source_chat_id: int, source_chat_title: str | None, user_id: int, questions: list[PollQuestion]) -> QuestionnaireSession | None:
    question_order, scored_questions_total = build_question_order(source_chat_id, user_id, questions)
    if not question_order: return None
    await _close_open_questionnaires(bot, source_chat_id, user_id)
    async with get_session() as session:
        return await create_questionnaire_session(session=session, questionnaire_in=QuestionnaireSessionCreate(
            source_chat_id=source_chat_id, source_chat_title=source_chat_title, user_id=user_id, delivery_chat_id=None, status="pending_start", question_order=question_order, total_questions=len(question_order), scored_questions_total=scored_questions_total, ))


async def _mark_questionnaire_pending(questionnaire_id: int) -> None:
    async with get_session() as session:
        questionnaire = await get_questionnaire_session(session, questionnaire_id)
        if questionnaire is None: return
        await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(delivery_chat_id=None, status="pending_start", current_question_id=None, active_poll_id=None, active_poll_message_id=None))
    _cancel_questionnaire_cleanup_task(questionnaire_id)
    _drop_tracked_questionnaire_messages(questionnaire_id)


async def _activate_questionnaire(questionnaire_id: int, delivery_chat_id: int, user_id: int) -> QuestionnaireSession | None:
    async with get_session() as session:
        questionnaire = await get_questionnaire_session_for_user(session, questionnaire_id, user_id)
        if questionnaire is None or questionnaire.status in {"cancelled", "completed"}: return None
        return await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(delivery_chat_id=delivery_chat_id, status="in_progress"))


async def _send_completion_message(bot: Bot, questionnaire_id: int, tracked: TrackedQuestionnaireMessages | None = None) -> None:
    async with get_session() as session:
        questionnaire = await get_questionnaire_session(session, questionnaire_id)
        if questionnaire is None or questionnaire.delivery_chat_id is None: return
        if questionnaire.status != "completed": questionnaire = await complete_questionnaire_session(session, questionnaire)
        delivery_thread_id = await _resolve_delivery_thread_id(session, questionnaire)
        if _is_group_delivery(questionnaire):
            completion_message = await bot.send_message(
                questionnaire.delivery_chat_id,
                build_group_completion_greeting(tracked.user_mention_html if tracked is not None else None),
                parse_mode=ParseMode.HTML,
                **_thread_kwargs(delivery_thread_id),
            )
            _schedule_ending_message_cleanup(bot, questionnaire.delivery_chat_id, completion_message.message_id)
            await delete_questionnaire_session(session, questionnaire)
            return
        await bot.send_message(questionnaire.delivery_chat_id, build_completion_message(questionnaire), reply_markup=_completion_reply_markup(questionnaire), **_thread_kwargs(delivery_thread_id))


async def _send_next_question(bot: Bot, questionnaire_id: int) -> bool:
    while True:
        async with get_session() as session:
            questionnaire = await get_questionnaire_session(session, questionnaire_id)
            if questionnaire is None or questionnaire.status in {"cancelled", "completed"} or questionnaire.delivery_chat_id is None: return False
            if questionnaire.current_question_index >= questionnaire.total_questions:
                await complete_questionnaire_session(session, questionnaire)
                break

            question_id = questionnaire.question_order[questionnaire.current_question_index]
            question = await get_question_with_answers(session, question_id)
            if question is None:
                await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(current_question_index=questionnaire.current_question_index + 1))
                continue

            prepared_question = prepare_question(question)
            if prepared_question is None:
                await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(current_question_index=questionnaire.current_question_index + 1))
                continue

            delivery_chat_id = questionnaire.delivery_chat_id
            delivery_thread_id = await _resolve_delivery_thread_id(session, questionnaire)
            position = questionnaire.current_question_index + 1
            total_questions = questionnaire.total_questions

        try: message = await bot.send_poll(chat_id=delivery_chat_id, question=build_question_text(prepared_question, position, total_questions), options=prepared_question.options, type="quiz" if prepared_question.is_scored else "regular", correct_option_id=prepared_question.correct_option_id, explanation=prepared_question.explanation, description=_build_poll_description(questionnaire_id), description_parse_mode=ParseMode.HTML, is_anonymous=False, allows_multiple_answers=False, **_thread_kwargs(delivery_thread_id), )
        except TelegramForbiddenError:
            await _mark_questionnaire_pending(questionnaire_id)
            return False

        except TelegramBadRequest:
            logger.exception("Failed to send poll for questionnaire %s", questionnaire_id)
            return False

        if message.poll is None:
            logger.error("Telegram did not return a poll for questionnaire %s", questionnaire_id)
            return False

        async with get_session() as session:
            questionnaire = await get_questionnaire_session(session, questionnaire_id)
            if questionnaire is None or questionnaire.status in {"cancelled", "completed"}: return False
            await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(delivery_chat_id=delivery_chat_id, status="in_progress", current_question_id=prepared_question.question_id, active_poll_id=message.poll.id, active_poll_message_id=message.message_id, ))
            if _is_group_delivery(questionnaire): track_questionnaire_message(questionnaire.id, delivery_chat_id, message.message_id)
        return True
    _cancel_questionnaire_cleanup_task(questionnaire_id)
    tracked = await _delete_tracked_questionnaire_messages(bot, questionnaire_id)
    await _send_completion_message(bot, questionnaire_id, tracked=tracked)
    return False


async def start_questionnaire_delivery(bot: Bot, questionnaire_id: int, delivery_chat_id: int, user_id: int, send_intro: bool) -> bool:
    questionnaire = await _activate_questionnaire(questionnaire_id, delivery_chat_id, user_id)
    if questionnaire is None: return False
    try:
        if send_intro: await bot.send_message(delivery_chat_id, build_private_intro(questionnaire), )
    except TelegramForbiddenError:
        await _mark_questionnaire_pending(questionnaire_id)
        return False

    if questionnaire.active_poll_id: return True
    return await _send_next_question(bot, questionnaire_id)


async def restart_questionnaire_for_user(bot: Bot, source_chat_id: int, user_id: int) -> QuestionnaireSession | None:
    moderated_chat = await get_moderated_chat(source_chat_id)
    if moderated_chat is None: return None
    return await create_pending_questionnaire(bot, moderated_chat.id, None, user_id, moderated_chat.questions)


async def handle_poll_answer(bot: Bot, answer: PollAnswer) -> None:
    if answer.user is None: return
    async with get_session() as session:
        questionnaire = await get_active_questionnaire_by_poll_id(session, answer.poll_id)
        if questionnaire is None or questionnaire.user_id != answer.user.id: return
        if questionnaire.current_question_id is None or questionnaire.delivery_chat_id is None: return
        question = await get_question_with_answers(session, questionnaire.current_question_id)
        if question is None:
            questionnaire = await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(current_question_index=questionnaire.current_question_index + 1, current_question_id=None, active_poll_id=None, active_poll_message_id=None, ))
            feedback_message = f"Вопрос пропущен. Прогресс: {questionnaire.current_question_index}/{questionnaire.total_questions}."
            delivery_chat_id = questionnaire.delivery_chat_id
            delivery_thread_id = await _resolve_delivery_thread_id(session, questionnaire)
            poll_message_id = questionnaire.active_poll_message_id
            questionnaire_id = questionnaire.id
            track_feedback_message = _is_group_delivery(questionnaire)

        else:
            existing_answer = await get_questionnaire_answer_for_session_and_question(session, questionnaire.id, question.id)
            if existing_answer is not None: return
            prepared_question = prepare_question(question)
            selected_option_index = answer.option_ids[0] if answer.option_ids else None
            selected_answer = question.variants[selected_option_index] if selected_option_index is not None and 0 <= selected_option_index < len(question.variants) else None
            is_correct = selected_option_index == prepared_question.correct_option_id if prepared_question is not None and prepared_question.is_scored else None
            await create_questionnaire_answer(session=session, answer_in=QuestionnaireAnswerCreate(session_id=questionnaire.id, question_id=question.id, selected_answer_id=selected_answer.id if selected_answer is not None else None, poll_id=answer.poll_id, question_text=question.text, selected_answer_text=selected_answer.text if selected_answer is not None else None, selected_option_index=selected_option_index, is_correct=is_correct, was_scored=bool(prepared_question and prepared_question.is_scored)))
            await create_user_record(session=session, record_in=UserRecordCreate( user_id=questionnaire.user_id, chat_id=questionnaire.source_chat_id, question=question.text, answer=selected_answer.text if selected_answer is not None else ""))
            questionnaire = await update_questionnaire_session(session=session, questionnaire=questionnaire, questionnaire_in=QuestionnaireSessionUpdate(current_question_index=questionnaire.current_question_index + 1, correct_answers_count=questionnaire.correct_answers_count + int(bool(is_correct)), current_question_id=None, active_poll_id=None, active_poll_message_id=None))
            feedback_message = f"Ответ принят. Прогресс: {questionnaire.current_question_index}/{questionnaire.total_questions}." if prepared_question is None else build_feedback_message(prepared_question, questionnaire.current_question_index, questionnaire.total_questions, is_correct)
            delivery_chat_id = questionnaire.delivery_chat_id
            delivery_thread_id = await _resolve_delivery_thread_id(session, questionnaire)
            poll_message_id = questionnaire.active_poll_message_id
            questionnaire_id = questionnaire.id
            track_feedback_message = _is_group_delivery(questionnaire)

    await stop_poll(bot, delivery_chat_id, poll_message_id)
    if track_feedback_message:
        await _send_next_question(bot, questionnaire_id)
        return
    await bot.send_message(delivery_chat_id, feedback_message, **_thread_kwargs(delivery_thread_id))
    await _send_next_question(bot, questionnaire_id)
