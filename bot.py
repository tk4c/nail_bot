# ============================================================
# bot.py — Точка входа: запуск бота
# ============================================================

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from scheduler import scheduler, restore_reminders

# Импорт роутеров
from handlers.user import router as user_router
from handlers.admin import router as admin_router

# ============================================================
# Настройка логирования
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Выполняется при запуске бота."""
    logger.info("Инициализация базы данных...")
    db.init_db()

    logger.info("Восстановление запланированных напоминаний...")
    await restore_reminders(bot)

    logger.info("Запуск планировщика задач...")
    scheduler.start()

    logger.info("✅ Бот успешно запущен!")


async def on_shutdown(bot: Bot):
    """Выполняется при остановке бота."""
    logger.info("Остановка планировщика...")
    scheduler.shutdown(wait=False)
    logger.info("Бот остановлен.")


async def main():
    """Основная функция запуска."""
    # Создаём бота с HTML-парсингом по умолчанию
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Создаём диспетчер с хранилищем состояний в памяти
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем роутеры (порядок важен: admin перед user)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Регистрируем хуки запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем polling
    logger.info("Запуск polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
