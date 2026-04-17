from pydantic import Field

from src.database.schemas.base import ORMSchema


class UserRecordBase(ORMSchema):
    user_id: int
    chat_id: int
    question: str = Field(min_length=1)
    answer: str = ""


class UserRecordCreate(UserRecordBase): pass


class UserRecordRead(UserRecordBase):
    id: int
