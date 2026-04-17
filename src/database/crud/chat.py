from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import ModeratedChat, PollQuestion
from src.database.schemas import ModeratedChatCreate, ModeratedChatUpdate


def _sort_chat_questions_by_id(chat: ModeratedChat | None) -> ModeratedChat | None:
    if chat is None: return None
    chat.questions.sort(key=lambda question: question.id)
    return chat


def _normalize_greetings_text(greetings_text: str) -> str:
    normalized = greetings_text.strip()
    if not normalized: raise ValueError("greetings_text must not be empty")
    return normalized


async def create_chat(session: AsyncSession, chat_in: ModeratedChatCreate) -> ModeratedChat:
    payload = chat_in.model_dump()
    payload["greetings_text"] = _normalize_greetings_text(payload["greetings_text"])
    chat = ModeratedChat(**payload)
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def get_chat(session: AsyncSession, chat_id: int) -> ModeratedChat | None: return await session.get(ModeratedChat, chat_id)


async def list_chats(session: AsyncSession) -> list[ModeratedChat]:
    result = await session.execute(select(ModeratedChat).order_by(ModeratedChat.id))
    return list(result.scalars().all())


async def get_chat_with_questions(session: AsyncSession, chat_id: int) -> ModeratedChat | None:
    result = await session.execute(select(ModeratedChat).where(ModeratedChat.id == chat_id).options(selectinload(ModeratedChat.questions)))
    return _sort_chat_questions_by_id(result.scalar_one_or_none())


async def get_chat_with_questions_and_answers(session: AsyncSession, chat_id: int) -> ModeratedChat | None:
    result = await session.execute(
        select(ModeratedChat).where(ModeratedChat.id == chat_id).options(
            selectinload(ModeratedChat.questions).selectinload(PollQuestion.variants),
            selectinload(ModeratedChat.questions).selectinload(PollQuestion.right_answer),
        )
    )
    return _sort_chat_questions_by_id(result.scalar_one_or_none())


async def get_or_create_chat(session: AsyncSession, chat_id: int, greetings_text: str | None = None) -> ModeratedChat:
    chat = await get_chat(session, chat_id)
    if chat is not None: return chat
    if greetings_text is None: raise ValueError("greetings_text is required to create a moderated chat")
    return await create_chat(session, ModeratedChatCreate(id=chat_id, greetings_text=_normalize_greetings_text(greetings_text)))


async def update_chat(session: AsyncSession, chat: ModeratedChat, chat_in: ModeratedChatUpdate) -> ModeratedChat:
    payload = chat_in.model_dump(exclude_unset=True)
    if "greetings_text" in payload and payload["greetings_text"] is not None:
        payload["greetings_text"] = _normalize_greetings_text(payload["greetings_text"])
    for field, value in payload.items(): setattr(chat, field, value)
    await session.commit()
    await session.refresh(chat)
    return chat


async def delete_chat(session: AsyncSession, chat_id: int) -> bool:
    chat = await get_chat(session, chat_id)
    if chat is None: return False
    await session.delete(chat)
    await session.commit()
    return True
