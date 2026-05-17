# ============================================================
# calendar_kb.py — Inline-календарь для выбора даты
# ============================================================

import calendar
from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db

# Русские названия месяцев
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

# Короткие названия дней недели
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def generate_calendar(year: int, month: int, prefix: str = "cal") -> InlineKeyboardMarkup:
    """
    Генерирует inline-клавиатуру с календарём на указанный месяц.

    prefix — для разделения пользовательского и админского календаря:
      'cal'   — пользовательский (запись)
      'adm'   — админский
    """
    today = date.today()
    max_date = today + timedelta(days=31)  # 1 месяц вперёд

    # Получаем рабочие дни мастера из БД
    work_days = set(db.get_work_days_in_month(year, month))

    rows: list[list[InlineKeyboardButton]] = []

    # Заголовок: « Месяц Год »
    header = [
        InlineKeyboardButton(text="«", callback_data=f"{prefix}_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="»", callback_data=f"{prefix}_next_{year}_{month}"),
    ]
    rows.append(header)

    # Дни недели
    rows.append([InlineKeyboardButton(text=d, callback_data="ignore") for d in DAYS_RU])

    # Дни месяца
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        week_row = []
        for day_num in week:
            if day_num == 0:
                week_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue

            d = date(year, month, day_num)
            day_str = d.isoformat()

            # Условия отображения
            is_past = d < today
            is_beyond = d > max_date
            is_work = day_str in work_days

            if is_past or is_beyond:
                # Прошедшие / слишком далёкие дни — неактивны
                week_row.append(
                    InlineKeyboardButton(text=f"{day_num}", callback_data="ignore")
                )
            elif is_work:
                # Рабочий день — активная кнопка с маркером
                week_row.append(
                    InlineKeyboardButton(
                        text=f"✅{day_num}",
                        callback_data=f"{prefix}_day_{day_str}",
                    )
                )
            else:
                # Нерабочий день — неактивная кнопка
                week_row.append(
                    InlineKeyboardButton(text=f"{day_num}", callback_data="ignore")
                )
        rows.append(week_row)

    # Кнопка «Назад» для возврата в меню
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_prev_month(year: int, month: int) -> tuple[int, int]:
    """Возвращает (год, месяц) для предыдущего месяца."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def get_next_month(year: int, month: int) -> tuple[int, int]:
    """Возвращает (год, месяц) для следующего месяца."""
    if month == 12:
        return year + 1, 1
    return year, month + 1
