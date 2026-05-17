# ============================================================
# scheduler.py — Автонапоминания за 24 часа до записи
#   Использует APScheduler (AsyncIOScheduler)
# ============================================================

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

import database as db
from config import REMINDER_HOURS_BEFORE, REMINDER_TEXT

# Глобальный экземпляр планировщика
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def send_reminder(bot: Bot, user_id: int, slot_time: str):
    """Отправляет напоминание пользователю."""
    try:
        text = REMINDER_TEXT.format(time=slot_time)
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        print(f"[REMINDER] Ошибка отправки напоминания user_id={user_id}: {e}")


async def schedule_reminder(
    bot: Bot, user_id: int, day_date: str, slot_time: str, booking_id: int
):
    """
    Планирует напоминание за REMINDER_HOURS_BEFORE часов до записи.
    Если до записи осталось менее 24 часов — напоминание НЕ создаётся.
    """
    # Парсим дату и время записи
    appointment_dt = datetime.strptime(f"{day_date} {slot_time}", "%Y-%m-%d %H:%M")
    reminder_dt = appointment_dt - timedelta(hours=REMINDER_HOURS_BEFORE)

    # Если время напоминания уже прошло — не создаём
    if reminder_dt <= datetime.now():
        print(
            f"[REMINDER] Напоминание для booking_id={booking_id} не создано: "
            "менее 24 часов до визита."
        )
        return

    job_id = f"reminder_{booking_id}"

    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=reminder_dt,
        args=[bot, user_id, slot_time],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,  # 1 час допуска
    )

    print(
        f"[REMINDER] Запланировано напоминание: "
        f"booking_id={booking_id}, user_id={user_id}, "
        f"дата отправки={reminder_dt}"
    )


def remove_reminder(booking_id: int):
    """Удаляет запланированное напоминание при отмене записи."""
    job_id = f"reminder_{booking_id}"
    try:
        scheduler.remove_job(job_id)
        print(f"[REMINDER] Удалено напоминание: booking_id={booking_id}")
    except Exception:
        pass  # Задача могла уже выполниться или не существовать


async def restore_reminders(bot: Bot):
    """
    Восстанавливает все напоминания из БД при перезапуске бота.
    Вызывается один раз при старте.
    """
    bookings = db.get_all_future_bookings()
    restored = 0

    for b in bookings:
        try:
            await schedule_reminder(
                bot=bot,
                user_id=b["user_id"],
                day_date=b["day_date"],
                slot_time=b["slot_time"],
                booking_id=b["id"],
            )
            restored += 1
        except Exception as e:
            print(f"[REMINDER] Ошибка восстановления booking_id={b['id']}: {e}")

    print(f"[REMINDER] Восстановлено напоминаний: {restored} из {len(bookings)}")
