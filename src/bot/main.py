from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
from src.bot.handlers import admin_router, user_router

if not TELEGRAM_BOT_TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router)
dp.include_router(user_router)
