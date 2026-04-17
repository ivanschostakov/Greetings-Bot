from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.helpers.user_records import UserRecordsChatOption, build_user_records_csv
from src.database import get_session
from src.database.crud import list_chats, list_user_records_for_chat

ADMIN_CHAT_STATUSES = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


def _resolve_chat_title(chat) -> str: return chat.full_name or getattr(chat, "title", None) or str(chat.id)
async def list_user_record_chats_for_admin(bot: Bot, user_id: int) -> list[UserRecordsChatOption]:
    async with get_session() as session: chats = await list_chats(session)

    available_chats: list[UserRecordsChatOption] = []
    for chat in chats:
        try:
            member = await bot.get_chat_member(chat.id, user_id)
            if member.status not in ADMIN_CHAT_STATUSES: continue
            chat_info = await bot.get_chat(chat.id)
        except (TelegramBadRequest, TelegramForbiddenError): continue
        available_chats.append(UserRecordsChatOption(chat_id=chat.id, title=_resolve_chat_title(chat_info)))
    available_chats.sort(key=lambda chat_option: chat_option.title.casefold())
    return available_chats


async def can_export_user_records(bot: Bot, user_id: int, chat_id: int) -> bool:
    try: member = await bot.get_chat_member(chat_id, user_id)
    except (TelegramBadRequest, TelegramForbiddenError): return False
    return member.status in ADMIN_CHAT_STATUSES


async def export_user_records_csv(chat_id: int) -> bytes:
    async with get_session() as session: records = await list_user_records_for_chat(session, chat_id)
    return build_user_records_csv(records)
