import io

from datetime import UTC, datetime, timedelta
from logging import getLogger
from random import Random

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatPermissions, Document, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from sqlalchemy import delete

from src.bot.helpers.configuration import ImportedQuestion, NEWCOMERS_TOPIC_NAME, NEWCOMER_RESTRICTION_MINUTES, build_questions_template
from src.database import get_session
from src.database.crud import get_chat as get_chat_crud
from src.database.models import ModeratedChat, PollAnswer, PollQuestion

logger = getLogger(__name__)

RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_manage_topics=False,
    can_edit_tag=False,
)


def describe_missing_permissions(member: ChatMemberAdministrator) -> list[str]:
    missing = []
    if not member.can_restrict_members: missing.append("право ограничивать участников")
    if not member.can_manage_topics: missing.append("право управлять темами")
    return missing


async def send_questions_template(bot: Bot, chat_id: int, *, reconfigure: bool, thread_id: int | None = None) -> None:
    intro = "Переходим к настройке заново." if reconfigure else "Начинаем настройку чата."
    await bot.send_message(chat_id, f"{intro}\n\nШаг 1/2. Заполни CSV-шаблон с вопросами и отправь его сюда обратно.", message_thread_id=thread_id)
    await bot.send_document(chat_id, build_questions_template(), caption="Формат колонок: question, wrong1, wrong2, wrong3, right", message_thread_id=thread_id)


async def read_uploaded_csv(bot: Bot, document: Document) -> bytes:
    buffer = io.BytesIO()
    await bot.download(document, destination=buffer)
    return buffer.getvalue()


async def is_chat_already_configured(chat_id: int) -> bool:
    async with get_session() as session: return await get_chat_crud(session, chat_id) is not None


async def is_user_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def finalize_chat_configuration(
    bot: Bot,
    chat_id: int,
    greeting_text: str,
    questions: list[ImportedQuestion],
    *,
    newcomers_thread_id: int | None = None,
) -> ModeratedChat:
    async with get_session() as session:
        chat = await session.get(ModeratedChat, chat_id)
        thread_id = newcomers_thread_id if newcomers_thread_id is not None else (chat.newcomers_thread_id if chat is not None else None)
        if thread_id is None:
            topic = await bot.create_forum_topic(chat_id, NEWCOMERS_TOPIC_NAME)
            thread_id = topic.message_thread_id
        if chat is None:
            chat = ModeratedChat(id=chat_id, greetings_text=greeting_text.strip(), newcomers_thread_id=thread_id)
            session.add(chat)
        else:
            chat.greetings_text = greeting_text.strip()
            chat.newcomers_thread_id = thread_id
        await session.execute(delete(PollQuestion).where(PollQuestion.chat_id == chat_id))
        await session.flush()
        for imported_question in questions:
            question = PollQuestion(chat_id=chat_id, text=imported_question.question, description=None, right_answer_id=None)
            session.add(question)
            await session.flush()
            options = [
                (imported_question.wrong1, False),
                (imported_question.wrong2, False),
                (imported_question.wrong3, False),
                (imported_question.right, True),
            ]
            Random(imported_question.question).shuffle(options)
            right_answer_id = None
            for answer_text, is_right in options:
                answer = PollAnswer(question_id=question.id, text=answer_text)
                session.add(answer)
                await session.flush()
                if is_right: right_answer_id = answer.id
            question.right_answer_id = right_answer_id
        await session.commit()
        await session.refresh(chat)
        return chat


async def restrict_newcomer(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=RESTRICTED_PERMISSIONS, until_date=datetime.now(UTC) + timedelta(minutes=NEWCOMER_RESTRICTION_MINUTES))
        return True
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.exception("Failed to restrict newcomer %s in chat %s", user_id, chat_id)
        return False


async def send_chat_message(
    bot: Bot,
    chat_id: int,
    text: str,
    thread_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardRemove | None = None,
    parse_mode: ParseMode | None = None,
) -> Message:
    try:
        return await bot.send_message(chat_id, text, message_thread_id=thread_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        if thread_id is None: raise
        logger.warning("Falling back to main chat because thread %s is unavailable in chat %s", thread_id, chat_id)
        return await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
