from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import UserRecord
from src.database.schemas import UserRecordCreate


async def create_user_record(session: AsyncSession, record_in: UserRecordCreate) -> UserRecord:
    record = UserRecord(**record_in.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_user_records_for_chat(session: AsyncSession, chat_id: int) -> list[UserRecord]:
    result = await session.execute(select(UserRecord).where(UserRecord.chat_id == chat_id).order_by(UserRecord.id))
    return list(result.scalars().all())
