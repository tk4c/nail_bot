# ============================================================
# config.py — Конфигурация бота
# ============================================================
import os

from decouple import config

# Токен бота (получить у @BotFather)
BOT_TOKEN = config("BOT_TOKEN")

# ID администратора (узнать через @userinfobot)
ADMIN_ID = config("ADMIN_ID", cast=int)

# ID канала для публикации расписания (формат: -100xxxxxxxxxx)
SCHEDULE_CHANNEL_ID = config("SCHEDULE_CHANNEL_ID", cast=int)

# ---- Проверка подписки на канал ----
# ID канала для проверки подписки (формат: -100xxxxxxxxxx)
CHANNEL_ID = config("CHANNEL_ID", cast=int)

# Ссылка на канал (для кнопки «Подписаться»)
CHANNEL_LINK = config("CHANNEL_LINK")

# ---- База данных ----
DATABASE_PATH = config("DATABASE_PATH", default="nail_bot.db")

# ---- Справочник услуг (id, название, цена) ----
# Используется для выбора при записи и в прайс-листе
SERVICES = {
    "french": {"name": "Френч", "price": 1000},
    "square": {"name": "Квадрат", "price": 500},
}


def build_price_text() -> str:
    """Генерирует прайс-лист из справочника услуг."""
    lines = ["💅 <b>Прайс-лист</b>", ""]
    for s in SERVICES.values():
        lines.append(f"▸ {s['name']} — <b>{s['price']:,} ₽</b>")
    lines += ["", "📩 Для записи нажмите <b>«Записаться»</b>"]
    return "\n".join(lines)


PRICE_TEXT = build_price_text()

# ---- Портфолио ----
PORTFOLIO_TEXT = "✨ Посмотрите мои работы:"
PORTFOLIO_URL = "https://ru.pinterest.com/crystalwithluv/_created/"

# ---- Напоминание ----
REMINDER_HOURS_BEFORE = 24
REMINDER_TEXT = (
    "🔔 <b>Напоминание</b>\n\n"
    "Напоминаем, что вы записаны на наращивание ресниц "
    "завтра в <b>{time}</b>.\n"
    "Ждём вас ❤️"
)
