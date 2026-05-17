# ============================================================
# config.py — Конфигурация бота
# ============================================================

# Токен бота (получить у @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# ID администратора (узнать через @userinfobot)
ADMIN_ID = 123456789

# ID канала для публикации расписания (формат: -100xxxxxxxxxx)
SCHEDULE_CHANNEL_ID = -1001234567890

# ---- Проверка подписки на канал ----
# ID канала для проверки подписки (формат: -100xxxxxxxxxx)
CHANNEL_ID = -1001234567890

# Ссылка на канал (для кнопки «Подписаться»)
CHANNEL_LINK = "https://t.me/your_channel"

# ---- База данных ----
DATABASE_PATH = "nail_bot.db"

# ---- Справочник услуг (id, название, цена) ----
# Используется для выбора при записи и в прайс-листе
SERVICES = {
    "french":  {"name": "Френч",  "price": 1000},
    "square":  {"name": "Квадрат", "price": 500},
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
