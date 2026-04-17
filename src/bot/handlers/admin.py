from logging import getLogger

from aiogram import F, Bot, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ChatMemberUpdated, Message

from src.bot.helpers.configuration import NEWCOMERS_TOPIC_NAME, deserialize_questions, parse_questions_csv, serialize_questions, validate_questions
from src.bot.services.configuration import (
    describe_missing_permissions, finalize_chat_configuration, is_chat_already_configured, is_user_chat_admin, read_uploaded_csv, send_questions_template,
)
from src.bot.states import ChatConfiguration

admin_router = Router(name="admin")
logger = getLogger(__name__)


@admin_router.my_chat_member()
async def bot_added_as_admin(update: ChatMemberUpdated, bot: Bot, state: FSMContext) -> None:
    if update.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP} or update.from_user is None: return
    if update.new_chat_member.status != ChatMemberStatus.ADMINISTRATOR or update.old_chat_member.status == ChatMemberStatus.ADMINISTRATOR: return
    missing_permissions = describe_missing_permissions(update.new_chat_member)
    if missing_permissions:
        await bot.send_message(update.chat.id, "Для настройки мне не хватает прав: " + ", ".join(missing_permissions) + ". Выдай их и запусти /configure.")
        return
    await state.clear()
    await state.set_state(ChatConfiguration.awaiting_questions_csv)
    await state.update_data(chat_id=update.chat.id, admin_id=update.from_user.id)
    await send_questions_template(bot, update.chat.id, reconfigure=await is_chat_already_configured(update.chat.id))


@admin_router.message(Command("configure"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def configure_chat(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None or not await is_user_chat_admin(bot, message.chat.id, message.from_user.id):
        await message.answer("Эту команду может запускать только админ чата.")
        return
    bot_member = await bot.get_chat_member(message.chat.id, bot.id)
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        await message.answer("Сначала выдай мне права администратора.")
        return
    missing_permissions = describe_missing_permissions(bot_member)
    if missing_permissions:
        await message.answer("Для настройки мне не хватает прав: " + ", ".join(missing_permissions) + ".")
        return
    await state.clear()
    await state.set_state(ChatConfiguration.awaiting_questions_csv)
    await state.update_data(chat_id=message.chat.id, admin_id=message.from_user.id)
    await send_questions_template(bot, message.chat.id, reconfigure=await is_chat_already_configured(message.chat.id))


@admin_router.message(ChatConfiguration.awaiting_questions_csv, F.document)
async def receive_questions_csv(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None or message.document is None: return
    data = await state.get_data()
    if data.get("chat_id") != message.chat.id or data.get("admin_id") != message.from_user.id: return
    try:
        raw_bytes = await read_uploaded_csv(bot, message.document)
        questions = parse_questions_csv(raw_bytes)
    except ValueError as error:
        await message.answer(f"Не удалось прочитать CSV: {error}")
        return
    validation_errors = validate_questions(questions)
    if validation_errors:
        await message.answer("Не удалось прочитать CSV:\n" + "\n".join(f"• {error}" for error in validation_errors))
        return
    await state.set_state(ChatConfiguration.awaiting_greeting_text)
    await state.update_data(questions=serialize_questions(questions))
    await message.answer(
        "Шаг 2/2. Теперь отправь приветственный текст для новичков. Можно с форматированием Telegram.\n\n"
        f"После этого я создам тему «{NEWCOMERS_TOPIC_NAME}», сохраню вопросы и включу сценарий модерации."
    )


@admin_router.message(ChatConfiguration.awaiting_questions_csv)
async def receive_questions_csv_fallback(message: Message) -> None:
    await message.answer("Сейчас я жду CSV-файл с колонками: question, wrong1, wrong2, wrong3, right.")


@admin_router.message(ChatConfiguration.awaiting_greeting_text, F.text)
async def receive_greeting_text(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None: return
    data = await state.get_data()
    if data.get("chat_id") != message.chat.id or data.get("admin_id") != message.from_user.id: return
    greeting_text = (message.html_text or "").strip()
    if not greeting_text:
        await message.answer("Приветственный текст не должен быть пустым.")
        return
    questions = deserialize_questions(data["questions"])
    validation_errors = validate_questions(questions)
    if validation_errors:
        await message.answer("Не удалось завершить настройку:\n" + "\n".join(f"• {error}" for error in validation_errors))
        await state.set_state(ChatConfiguration.awaiting_questions_csv)
        await message.answer("Отправь CSV заново с исправленными вопросами.")
        return
    try:
        chat = await finalize_chat_configuration(bot, message.chat.id, greeting_text, questions)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.exception("Failed to finalize chat configuration for %s", message.chat.id)
        await message.answer(f"Не удалось завершить настройку: {error}. Проверь, что это supergroup с включёнными темами и у меня есть право управлять темами.")
        return
    await state.clear()
    await message.answer(
        "Чат настроен.\n\n"
        f"Тема для новичков: «{NEWCOMERS_TOPIC_NAME}».\n"
        "Новые участники будут получать опрос, приветствие и ограничение на сообщения на 5 минут."
        + (f"\nID темы: {chat.newcomers_thread_id}" if chat.newcomers_thread_id is not None else "")
    )


@admin_router.message(ChatConfiguration.awaiting_greeting_text)
async def receive_greeting_text_fallback(message: Message) -> None:
    await message.answer("Сейчас я жду текст приветствия для новичков.")
