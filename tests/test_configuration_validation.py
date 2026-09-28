import unittest

from aiogram.types import User
from datetime import UTC, datetime
from types import SimpleNamespace

from src.bot.helpers.configuration import ImportedQuestion, validate_questions
from src.bot.helpers.questionnaire import (
    MASKED_MENTION_TEXT, PreparedQuestion, build_feedback_message, build_group_completion_greeting, build_group_greeting,
    build_group_timeout_greeting, build_start_keyboard,
)
from src.bot.helpers.user_records import (
    UserRecordsChatOption, build_user_records_csv, build_user_records_keyboard, parse_user_records_callback,
)
from src.bot.services.questionnaire import (
    ENDING_MESSAGE_TTL, TRACKED_MESSAGE_TTL, _build_poll_description, _completion_reply_markup, _thread_kwargs, _tracked_questionnaire_messages,
    track_questionnaire_message,
)


class ConfigurationValidationTests(unittest.TestCase):
    def tearDown(self) -> None:
        _tracked_questionnaire_messages.clear()

    def test_validate_questions_reports_too_long_answer(self) -> None:
        questions = [
            ImportedQuestion(
                question="Что такое мг и мл?",
                wrong1="короткий ответ",
                wrong2="Мг — это вес (сухого пептида в виале или доза пептида), а мл - это объем (воды для разведения или раствора с пептидом).",
                wrong3="ещё один короткий ответ",
                right="верный ответ",
            )
        ]

        errors = validate_questions(questions)

        self.assertEqual(
            errors,
            ["Вопрос 1: вариант ответа в колонке wrong2 длиннее 100 символов."],
        )

    def test_build_group_greeting_escapes_name_without_mention(self) -> None:
        user = User(id=42, is_bot=False, first_name="Alice & Bob")
        greeting = build_group_greeting(user, "<i>Привет</i>")

        self.assertEqual(
            greeting,
            'Добро пожаловать, Alice &amp; Bob!\n\n<i>Привет</i>',
        )

    def test_build_group_completion_greeting_is_cute(self) -> None:
        self.assertEqual(
            build_group_completion_greeting('<a href="tg://user?id=42">Alice</a>'),
            'Спасибо, что ответили на все вопросы, <a href="tg://user?id=42">Alice</a>. Очень рады вам в чате!',
        )

    def test_build_group_timeout_greeting_mentions_missed_answers(self) -> None:
        self.assertEqual(
            build_group_timeout_greeting('<a href="tg://user?id=42">Alice</a>'),
            'Немного жаль, что вы не ответили на вопросы, <a href="tg://user?id=42">Alice</a>, но мы всё равно очень рады вам в чате!',
        )

    def test_build_start_keyboard_uses_start_link_url(self) -> None:
        keyboard = build_start_keyboard("https://t.me/testbot?start=questionnaire_10")

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "Открыть бота")
        self.assertEqual(keyboard.inline_keyboard[0][0].url, "https://t.me/testbot?start=questionnaire_10")

    def test_build_feedback_message_does_not_repeat_correctness(self) -> None:
        question = PreparedQuestion(
            question_id=1,
            text="Вопрос",
            options=["A", "B"],
            correct_option_id=0,
            correct_answer_text="A",
            explanation="Пояснение",
        )

        feedback = build_feedback_message(question, 2, 5, True)

        self.assertEqual(feedback, "Ответ принят.\n\nПрогресс: 2/5.\n\nПояснение")
        self.assertNotIn("Верно", feedback)
        self.assertNotIn("Неверно", feedback)

    def test_tracked_questionnaire_message_ttl_is_three_hours(self) -> None:
        self.assertEqual(TRACKED_MESSAGE_TTL.total_seconds(), 3 * 60 * 60)

    def test_track_questionnaire_message_expires_after_cleanup_window(self) -> None:
        now = datetime.now(UTC)

        self.assertTrue(track_questionnaire_message(10, -1001, 101, now=now))
        self.assertFalse(track_questionnaire_message(10, -1001, 102, now=now + TRACKED_MESSAGE_TTL))
        self.assertNotIn(10, _tracked_questionnaire_messages)

    def test_build_poll_description_uses_tracked_user_mention(self) -> None:
        track_questionnaire_message(
            10,
            -1001,
            None,
            user_mention_html='<a href="tg://user?id=42">Alice</a>',
        )

        self.assertEqual(
            _build_poll_description(10),
            'Для <a href="tg://user?id=42">Alice</a>',
        )

    def test_track_questionnaire_message_can_store_only_mention_without_message_id(self) -> None:
        self.assertTrue(
            track_questionnaire_message(
                10,
                -1001,
                None,
                user_mention_html='<a href="tg://user?id=42">Alice</a>',
            )
        )
        self.assertEqual(_tracked_questionnaire_messages[10].message_ids, set())

    def test_thread_kwargs_include_message_thread_id_only_when_present(self) -> None:
        self.assertEqual(_thread_kwargs(None), {})
        self.assertEqual(_thread_kwargs(777), {"message_thread_id": 777})

    def test_ending_message_ttl_is_thirty_seconds(self) -> None:
        self.assertEqual(ENDING_MESSAGE_TTL.total_seconds(), 30)

    def test_completion_reply_markup_is_hidden_for_group_delivery(self) -> None:
        group_session = SimpleNamespace(source_chat_id=-1001, delivery_chat_id=-1001)
        private_session = SimpleNamespace(source_chat_id=-1001, delivery_chat_id=42)

        self.assertIsNone(_completion_reply_markup(group_session))
        self.assertEqual(
            _completion_reply_markup(private_session).inline_keyboard[0][0].callback_data,
            "restart:-1001",
        )

    def test_build_user_records_keyboard_uses_expected_callback_prefix(self) -> None:
        keyboard = build_user_records_keyboard([UserRecordsChatOption(chat_id=-1001, title="Main Chat")])

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "Main Chat")
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "user_records:-1001")

    def test_parse_user_records_callback_returns_chat_id(self) -> None:
        self.assertEqual(parse_user_records_callback("user_records:-1001"), -1001)
        self.assertIsNone(parse_user_records_callback("user_records:"))
        self.assertIsNone(parse_user_records_callback("restart:-1001"))

    def test_build_user_records_csv_includes_expected_columns(self) -> None:
        csv_bytes = build_user_records_csv(
            [SimpleNamespace(id=1, user_id=42, chat_id=-1001, question="Как вас зовут?", answer="Алиса")]
        )

        self.assertEqual(
            csv_bytes.decode("utf-8-sig"),
            "id,user_id,chat_id,question,answer\n1,42,-1001,Как вас зовут?,Алиса\n",
        )


if __name__ == "__main__":
    unittest.main()
