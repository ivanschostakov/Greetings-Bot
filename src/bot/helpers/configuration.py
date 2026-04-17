from __future__ import annotations

import csv
import io

from dataclasses import asdict, dataclass

from aiogram.types import BufferedInputFile

CSV_HEADERS = ("question", "wrong1", "wrong2", "wrong3", "right")
MAX_QUESTION_LENGTH = 255
MAX_ANSWER_LENGTH = 100
NEWCOMERS_TOPIC_NAME = "для новичков"
NEWCOMER_RESTRICTION_MINUTES = 5


@dataclass(slots=True)
class ImportedQuestion:
    question: str
    wrong1: str
    wrong2: str
    wrong3: str
    right: str


def build_questions_template() -> BufferedInputFile:
    content = ",".join(CSV_HEADERS) + "\n"
    return BufferedInputFile(content.encode("utf-8"), filename="questions_template.csv")


def parse_questions_csv(raw_bytes: bytes) -> list[ImportedQuestion]:
    text = _decode_csv_bytes(raw_bytes)
    try: dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;") if text.strip() else csv.get_dialect("excel")
    except csv.Error: dialect = csv.get_dialect("excel")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    fieldnames = [_normalize_header(name) for name in reader.fieldnames or []]
    if tuple(fieldnames) != CSV_HEADERS: raise ValueError("CSV must have headings: question, wrong1, wrong2, wrong3, right")
    questions = [_parse_row(index, row) for index, row in enumerate(reader, start=2) if any(_normalize_value(value) for value in row.values())]
    if not questions: raise ValueError("CSV must contain at least one question row")
    return questions


def serialize_questions(questions: list[ImportedQuestion]) -> list[dict[str, str]]: return [asdict(question) for question in questions]
def deserialize_questions(payload: list[dict[str, str]]) -> list[ImportedQuestion]: return [ImportedQuestion(**row) for row in payload]


def validate_questions(questions: list[ImportedQuestion]) -> list[str]:
    errors: list[str] = []
    for index, question in enumerate(questions, start=1):
        prefix = f"Вопрос {index}"
        if len(question.question) > MAX_QUESTION_LENGTH: errors.append(f"{prefix}: текст в колонке question длиннее {MAX_QUESTION_LENGTH} символов.")
        for column in ("wrong1", "wrong2", "wrong3", "right"):
            value = getattr(question, column)
            if len(value) > MAX_ANSWER_LENGTH: errors.append(f"{prefix}: вариант ответа в колонке {column} длиннее {MAX_ANSWER_LENGTH} символов.")
    return errors


def _decode_csv_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251", "utf-8"):
        try: return raw_bytes.decode(encoding)
        except UnicodeDecodeError: continue
    raise ValueError("CSV must be encoded as UTF-8 or CP1251")


def _normalize_header(value: str | None) -> str: return (value or "").strip().lower()
def _normalize_value(value: str | None) -> str: return (value or "").strip()


def _parse_row(index: int, row: dict[str, str | None]) -> ImportedQuestion:
    normalized = {key: _normalize_value(value) for key, value in row.items()}
    if any(not normalized[column] for column in CSV_HEADERS): raise ValueError(f"Row {index} must have all columns filled")
    return ImportedQuestion(**{column: normalized[column] for column in CSV_HEADERS})
