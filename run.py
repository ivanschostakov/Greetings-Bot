from logging import getLogger

from config import DROP_PENDING_UPDATES
from logger import setup_logging
from src.bot.main import bot, dp

logger = getLogger(__name__)


async def main() -> None:
    logger.info("Starting Greetings Bot")
    await bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    try: await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally: await bot.session.close()

if __name__ == "__main__":
    setup_logging()
    import asyncio
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
