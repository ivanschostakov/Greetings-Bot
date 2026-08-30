from dataclasses import dataclass
from html import escape
from logging import getLogger
from random import Random

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, User

from src.database.models import PollQuestion, QuestionnaireSession

QUESTIONNAIRE_PAYLOAD_PREFIX = "questionnaire_"
RESTART_CALLBACK_PREFIX = "restart:"
MASKED_MENTION_TEXT = "ㅤㅤ"
logger = getLogger(__name__)


@dataclass(slots=True)
class PreparedQuestion:
    question_id: int
    text: str
    options: list[str]
    correct_option_id: int | None
    correct_answer_text: str | None
    explanation: str | None

    @property
    def is_scored(self) -> bool: return self.correct_option_id is not None


def clean_text(text: str | None) -> str | None:
    if text is None: return None
    normalized = text.strip()
    return normalized or None


def prepare_question(question: PollQuestion) -> PreparedQuestion | None:
    question_text = clean_text(question.text)
    if question_text is None:
        logger.warning("Question %s skipped because it has no text", question.id)
        return None

    options = [clean_text(answer.text) for answer in question.variants]
    if len(options) < 2 or any(option is None for option in options):
        logger.warning("Question %s skipped because it has invalid variants", question.id)
        return None

    correct_option_id = None
    correct_answer_text = None
    if question.right_answer_id is not None:
        if question.right_answer is None:
            logger.warning("Question %s skipped because right_answer is missing", question.id)
            return None

        for index, answer in enumerate(question.variants):
            if answer.id != question.right_answer.id: continue
            correct_option_id = index
            correct_answer_text = clean_text(answer.text)
            break

        if correct_option_id is None or correct_answer_text is None:
            logger.warning("Question %s skipped because right_answer is not in variants", question.id)
            return None

    return PreparedQuestion(question.id, question_text, [option for option in options if option is not None], correct_option_id, correct_answer_text, clean_text(question.description))


def build_question_order(chat_id: int, user_id: int, questions: list[PollQuestion]) -> tuple[list[int], int]:
    prepared_questions = [prepared for question in questions if (prepared := prepare_question(question)) is not None]
    question_order = [prepared.question_id for prepared in prepared_questions]
    Random(f"{chat_id}:{user_id}").shuffle(question_order)
    return question_order, sum(prepared.is_scored for prepared in prepared_questions)


def build_user_mention_html(user: User) -> str:
    return f'<a href="tg://user?id={user.id}">{MASKED_MENTION_TEXT}</a><b>{escape(user.full_name)}</b>'
def build_group_greeting(user: User, greetings_text: str) -> str: return f"Добро пожаловать, {build_user_mention_html(user)}!\n\n{greetings_text}"
def build_group_completion_greeting(user_mention_html: str | None) -> str:
    if user_mention_html: return f"Спасибо, что ответили на все вопросы, {user_mention_html}. Очень рады вам в чате!"
    return "Спасибо, что ответили на все вопросы. Очень рады вам в чате!"


def build_group_timeout_greeting(user_mention_html: str | None) -> str:
    if user_mention_html: return f"Немного жаль, что вы не ответили на вопросы, {user_mention_html}, но мы всё равно очень рады вам в чате!"
    return "Немного жаль, что вы не ответили на вопросы, но мы всё равно очень рады вам в чате!"


def build_private_intro(questionnaire: QuestionnaireSession) -> str:
    if questionnaire.source_chat_title: return f"Начинаем опрос для чата «{questionnaire.source_chat_title}»."
    return "Начинаем опрос."


def build_question_text(question: PreparedQuestion, position: int, total_questions: int) -> str: return f"Вопрос {position}/{total_questions}\n\n{question.text}"
def build_feedback_message(question: PreparedQuestion, answered_questions: int, total_questions: int, is_correct: bool | None) -> str:
    lines = ["Ответ принят."]
    lines.append(f"Прогресс: {answered_questions}/{total_questions}.")
    if question.explanation: lines.append(question.explanation)
    return "\n\n".join(lines)


def build_completion_message(questionnaire: QuestionnaireSession) -> str:
    header = f"Опрос для чата «{questionnaire.source_chat_title}» завершён." if questionnaire.source_chat_title else "Опрос завершён."
    summary = f"Вы ответили на {questionnaire.total_questions} вопросов."
    if questionnaire.scored_questions_total: summary = f"{summary}\nПравильных ответов: {questionnaire.correct_answers_count}/{questionnaire.scored_questions_total}."
    return f"{header}\n\n{summary}"


def build_restart_keyboard(source_chat_id: int) -> InlineKeyboardMarkup: return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пройти заново", callback_data=f"{RESTART_CALLBACK_PREFIX}{source_chat_id}")]])
def build_start_keyboard(start_link: str) -> InlineKeyboardMarkup: return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть бота", url=start_link)]])
def build_questionnaire_payload(questionnaire_id: int) -> str: return f"{QUESTIONNAIRE_PAYLOAD_PREFIX}{questionnaire_id}"


def parse_questionnaire_payload(payload: str | None) -> int | None:
    if payload is None or not payload.startswith(QUESTIONNAIRE_PAYLOAD_PREFIX): return None
    raw_id = payload.removeprefix(QUESTIONNAIRE_PAYLOAD_PREFIX)
    if not raw_id: return None
    try: return int(raw_id)
    except ValueError: return None
