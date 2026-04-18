from logging import getLogger

from aiogram import F, Bot, Router
from aiogram.enums import ParseMode
from aiogram.enums import ChatType
from aiogram.filters import CommandObject, CommandStart, IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter, Command
from aiogram.types import BufferedInputFile, CallbackQuery, ChatMemberUpdated, Message, PollAnswer

from src.bot.helpers.configuration import NEWCOMER_RESTRICTION_MINUTES
from src.bot.helpers.questionnaire import RESTART_CALLBACK_PREFIX, build_group_greeting, build_start_keyboard, parse_questionnaire_payload
from src.bot.helpers.user_records import USER_RECORDS_CALLBACK_PREFIX, build_user_records_keyboard, parse_user_records_callback
from src.bot.services.configuration import restrict_newcomer, send_chat_message
from src.bot.services.questionnaire import (
    build_questionnaire_start_link, consume_questionnaire_link, create_pending_questionnaire,
    get_latest_resumable_questionnaire, get_moderated_chat, handle_poll_answer, restart_questionnaire_for_user,
    schedule_questionnaire_cleanup, start_questionnaire_delivery, track_questionnaire_message,
)
from src.bot.services.user_records import can_export_user_records, export_user_records_csv, list_user_record_chats_for_admin

user_router = Router(name="user")
logger = getLogger(__name__)


@user_router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def chat_member_updated(update: ChatMemberUpdated, bot: Bot) -> None:
    chat = update.chat
    user = update.new_chat_member.user
    if user.is_bot: return
    moderated_chat = await get_moderated_chat(chat.id)
    if moderated_chat is None:
        logger.info("Chat %s is not configured for moderation", chat.id)
        return

    restriction_enabled = await restrict_newcomer(bot, chat.id, user.id)
    questionnaire = await create_pending_questionnaire(bot, chat.id, chat.title, user.id, moderated_chat.questions)
    greeting = build_group_greeting(user, moderated_chat.greetings_text)

    if restriction_enabled: greeting = f"{greeting}\n\nПисать в чате можно будет через {NEWCOMER_RESTRICTION_MINUTES} минут."
    thread_id = moderated_chat.newcomers_thread_id
    await send_chat_message(bot, chat.id, greeting, thread_id=thread_id, parse_mode=ParseMode.HTML)
    if questionnaire is None:
        logger.warning("No valid questions configured for chat %s", chat.id)
        return

    start_link = await build_questionnaire_start_link(bot, questionnaire.id)
    start_message = await send_chat_message(
        bot,
        chat.id,
        "Чтобы пройти опрос, нажми кнопку ниже и ответь мне в личке.",
        thread_id=thread_id,
        reply_markup=build_start_keyboard(start_link),
    )

    track_questionnaire_message(
        questionnaire.id,
        chat.id,
        start_message.message_id,
        user_mention_html=user.mention_html(),
    )

    schedule_questionnaire_cleanup(bot, questionnaire.id)


@user_router.message(F.chat.type == ChatType.PRIVATE, CommandStart())
async def start_private_questionnaire(message: Message, command: CommandObject | None, bot: Bot) -> None:
    if message.from_user is None: return
    questionnaire_id = parse_questionnaire_payload(command.args if command else None)
    if questionnaire_id is not None:
        await consume_questionnaire_link(bot, questionnaire_id)
        if await start_questionnaire_delivery(bot, questionnaire_id, message.chat.id, message.from_user.id, send_intro=True): return
        await message.answer("Не удалось запустить этот опрос. Возможно, он уже завершён.")
        return

    admin_chat_options = await list_user_record_chats_for_admin(bot, message.from_user.id)
    if admin_chat_options:
        await message.answer(
            "Выберите чат, чтобы получить CSV с ответами пользователей.",
            reply_markup=build_user_records_keyboard(admin_chat_options),
        )

    questionnaire = await get_latest_resumable_questionnaire(message.from_user.id)
    if admin_chat_options and questionnaire is None: return
    if questionnaire is None:
        await message.answer("Я приветствую новых участников и провожу опросы. Добавь меня в чат и настрой вопросы в базе.")
        return

    if questionnaire.active_poll_id:
        await message.answer("Я уже отправил тебе текущий вопрос. Ответь на него, чтобы продолжить.")
        return

    if await start_questionnaire_delivery(bot, questionnaire.id, message.chat.id, message.from_user.id, send_intro=questionnaire.current_question_index == 0): return
    await message.answer("Пока не получилось продолжить опрос. Попробуй ещё раз чуть позже.")


@user_router.poll_answer()
async def poll_answer_received(answer: PollAnswer, bot: Bot) -> None: await handle_poll_answer(bot, answer)


@user_router.callback_query(F.message.chat.type == ChatType.PRIVATE, F.data.startswith(USER_RECORDS_CALLBACK_PREFIX))
async def export_user_records(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return

    chat_id = parse_user_records_callback(callback.data)
    if chat_id is None:
        await callback.answer("Не удалось определить чат.", show_alert=True)
        return

    if not await can_export_user_records(bot, callback.from_user.id, chat_id):
        await callback.answer("Эта выгрузка вам недоступна.", show_alert=True)
        return

    csv_bytes = await export_user_records_csv(chat_id)
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=f"user_records_{abs(chat_id)}.csv"),
        caption="Выгрузка ответов пользователей.",
    )

    await callback.answer("Отправляю CSV.")


@user_router.callback_query(F.message.chat.type == ChatType.PRIVATE, F.data.startswith(RESTART_CALLBACK_PREFIX))
async def restart_questionnaire(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return

    raw_chat_id = callback.data.removeprefix(RESTART_CALLBACK_PREFIX)
    try: source_chat_id = int(raw_chat_id)
    except ValueError:
        await callback.answer("Не удалось перезапустить опрос.", show_alert=True)
        return

    questionnaire = await restart_questionnaire_for_user(bot, source_chat_id, callback.from_user.id)
    if questionnaire is None:
        await callback.answer("Опрос больше недоступен.", show_alert=True)
        return

    if await start_questionnaire_delivery(bot, questionnaire.id, callback.message.chat.id, callback.from_user.id, send_intro=True):
        await callback.answer("Запускаю опрос заново.")
        return

    await callback.answer("Не удалось начать опрос заново.", show_alert=True)


@user_router.message(F.chat.type == ChatType.PRIVATE, Command("test"))
async def test_command(message: Message) -> None:
    logger.info("test_command " + message.from_user.mention_html(""))
    if message.from_user is None: return
    await message.answer(message.from_user.mention_html("ㅤㅤㅤㅤㅤㅤ"), parse_mode=ParseMode.HTML)
