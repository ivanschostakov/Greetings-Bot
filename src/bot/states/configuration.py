from aiogram.fsm.state import State, StatesGroup


class ChatConfiguration(StatesGroup):
    awaiting_questions_csv = State()
    awaiting_greeting_text = State()
