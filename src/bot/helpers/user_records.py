import csv
from dataclasses import dataclass
from io import StringIO
from typing import Protocol, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

USER_RECORDS_CALLBACK_PREFIX = "user_records:"


class UserRecordRow(Protocol):
    id: int
    user_id: int
    chat_id: int
    question: str
    answer: str


@dataclass(slots=True)
class UserRecordsChatOption:
    chat_id: int
    title: str


def build_user_records_keyboard(chat_options: Sequence[UserRecordsChatOption]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=chat_option.title, callback_data=f"{USER_RECORDS_CALLBACK_PREFIX}{chat_option.chat_id}")]
            for chat_option in chat_options
        ]
    )


def parse_user_records_callback(data: str | None) -> int | None:
    if data is None or not data.startswith(USER_RECORDS_CALLBACK_PREFIX):
        return None
    raw_chat_id = data.removeprefix(USER_RECORDS_CALLBACK_PREFIX)
    if not raw_chat_id:
        return None
    try:
        return int(raw_chat_id)
    except ValueError:
        return None


def build_user_records_csv(records: Sequence[UserRecordRow]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=("id", "user_id", "chat_id", "question", "answer"), lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                "id": record.id,
                "user_id": record.user_id,
                "chat_id": record.chat_id,
                "question": record.question,
                "answer": record.answer,
            }
        )
    return buffer.getvalue().encode("utf-8-sig")
