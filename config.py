from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = getenv("TELEGRAM_BOT_TOKEN")
POSTGRES_DB = getenv("POSTGRES_DB")
POSTGRES_USER = getenv("POSTGRES_USER")
POSTGRES_PORT = int(getenv("POSTGRES_PORT", 0))
POSTGRES_HOST = getenv("POSTGRES_HOST")
POSTGRES_PASSWORD = getenv("POSTGRES_PASSWORD")
DB_HOST = POSTGRES_HOST or "localhost"
DB_HOST_WITH_PORT = f"{DB_HOST}:{POSTGRES_PORT}" if POSTGRES_PORT else DB_HOST
SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST_WITH_PORT}/{POSTGRES_DB}"
ASYNC_DB_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST_WITH_PORT}/{POSTGRES_DB}"
DROP_PENDING_UPDATES = getenv("DROP_PENDING_UPDATES", "0") == "1"
WORKING_DIR = Path(__file__).parent
LOGS_DIR = WORKING_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
