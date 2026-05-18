# ============================================================
# handlers/admin.py — Админ-панель (доступ только по ADMIN_ID)
#   • Добавление рабочих дней
#   • Добавление / удаление слотов
#   • Отмена записей клиентов
#   • Закрытие дня целиком
#   • Просмотр расписания на дату
# ============================================================

import re
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import database as db
from calendar_kb import generate_calendar, get_next_month, get_prev_month
from config import ADMIN_ID, SERVICES
from states import AdminFSM

router = Router()


# ============================================================
# Проверка прав администратора (фильтр)
# ============================================================


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID


# ============================================================
# Админ-меню
# ============================================================


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Добавить рабочий день", callback_data="adm_add_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🕐 Управление слотами", callback_data="adm_manage_slots"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Просмотр расписания", callback_data="adm_view_schedule"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Закрыть день", callback_data="adm_close_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена записи клиента", callback_data="adm_cancel_booking"
                )
            ],
        ]
    )


ADMIN_WELCOME = "🔧 <b>Админ-панель</b>\n\nВыберите действие:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Команда /admin — вход в админ-панель."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer(ADMIN_WELCOME, reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в админ-меню."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        ADMIN_WELCOME, reply_markup=admin_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# Добавление рабочего дня
# ============================================================


@router.callback_query(F.data == "adm_add_day")
async def cb_adm_add_day(callback: CallbackQuery, state: FSMContext):
    """Показываем админский календарь для добавления рабочего дня."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    today = date.today()
    await state.set_state(AdminFSM.choosing_date)
    await state.update_data(adm_action="add_day")

    await callback.message.edit_text(
        "📅 <b>Выберите дату для добавления рабочего дня:</b>",
        reply_markup=generate_calendar(today.year, today.month, prefix="adm"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Навигация по админскому календарю
# ============================================================


@router.callback_query(F.data.startswith("adm_prev_"))
async def cb_adm_prev(callback: CallbackQuery):
    """Предыдущий месяц в админском календаре."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    new_year, new_month = get_prev_month(year, month)
    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar(new_year, new_month, prefix="adm")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_next_"))
async def cb_adm_next(callback: CallbackQuery):
    """Следующий месяц в админском календаре."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    new_year, new_month = get_next_month(year, month)
    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar(new_year, new_month, prefix="adm")
    )
    await callback.answer()


# ============================================================
# Обработка выбора даты в админском календаре
# ============================================================


@router.callback_query(F.data.startswith("adm_day_"))
async def cb_adm_day(callback: CallbackQuery, state: FSMContext):
    """Админ выбрал дату — определяем действие из FSM-контекста."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    day_date = callback.data.replace("adm_day_", "")
    data = await state.get_data()
    action = data.get("adm_action", "")

    if action == "add_day":
        # Добавляем рабочий день
        db.add_work_day(day_date)
        await callback.message.edit_text(
            f"✅ <b>{day_date}</b> добавлен как рабочий день.\n\n"
            "Теперь добавьте временные слоты через «Управление слотами».",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🕐 Управление слотами",
                            callback_data="adm_manage_slots",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Админ-меню", callback_data="adm_menu"
                        )
                    ],
                ]
            ),
            parse_mode="HTML",
        )
        await state.clear()

    elif action == "manage_slots":
        # Показываем слоты на выбранную дату
        await state.update_data(adm_day_date=day_date)
        await show_slot_management(callback, day_date)

    elif action == "view_schedule":
        # Показываем расписание на дату
        await show_schedule(callback, day_date)

    elif action == "close_day":
        # Подтверждение закрытия дня
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, закрыть",
                        callback_data=f"adm_confirm_close_{day_date}",
                    ),
                    InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"),
                ],
            ]
        )
        await callback.message.edit_text(
            f"⚠️ <b>Закрыть день {day_date}?</b>\n\n"
            "Все слоты и записи на эту дату будут удалены!",
            reply_markup=kb,
            parse_mode="HTML",
        )

    elif action == "cancel_booking":
        # Показываем записи на дату для отмены
        await show_bookings_for_cancel(callback, day_date)

    await callback.answer()


# ============================================================
# Управление слотами
# ============================================================


@router.callback_query(F.data == "adm_manage_slots")
async def cb_adm_manage_slots(callback: CallbackQuery, state: FSMContext):
    """Открываем календарь для выбора дня для управления слотами."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    today = date.today()
    await state.set_state(AdminFSM.choosing_date)
    await state.update_data(adm_action="manage_slots")

    await callback.message.edit_text(
        "📅 <b>Выберите дату для управления слотами:</b>",
        reply_markup=generate_calendar(today.year, today.month, prefix="adm"),
        parse_mode="HTML",
    )
    await callback.answer()


def _service_name(service_id: str | None) -> str:
    """Возвращает название услуги по ID (для отображения в админке)."""
    if not service_id:
        return ""
    svc = SERVICES.get(service_id)
    return svc["name"] if svc else service_id


async def show_slot_management(callback: CallbackQuery, day_date: str):
    """Показывает текущие слоты и кнопки управления."""
    slots = db.get_all_slots(day_date)

    text = f"🕐 <b>Слоты на {day_date}:</b>\n\n"
    buttons = []

    if slots:
        for s in slots:
            if s["client_name"] is None:
                status = "🟢 Свободно"
            else:
                svc = _service_name(s.get("service_id"))
                status = (
                    f"🔴 {s['client_name']} ({svc})"
                    if svc
                    else f"🔴 {s['client_name']}"
                )
            text += f"▸ {s['slot_time']} — {status}\n"
            # Кнопка удаления слота
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"🗑 Удалить {s['slot_time']}",
                        callback_data=f"adm_del_slot_{day_date}_{s['slot_time']}",
                    )
                ]
            )
    else:
        text += "<i>Слотов пока нет</i>\n"

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить слот", callback_data=f"adm_add_slot_{day_date}"
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")]
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_add_slot_"))
async def cb_adm_add_slot(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода времени нового слота."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    day_date = callback.data.replace("adm_add_slot_", "")
    await state.update_data(adm_day_date=day_date)
    await state.set_state(AdminFSM.adding_slot_time)

    await callback.message.edit_text(
        f"🕐 <b>Добавление слота на {day_date}</b>\n\n"
        "Введите время в формате <b>HH:MM</b>\n"
        "Например: <code>10:00</code>, <code>14:30</code>\n\n"
        "Или несколько через запятую: <code>10:00, 11:00, 12:00</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminFSM.adding_slot_time)
async def msg_add_slot_time(message: Message, state: FSMContext):
    """Обработка ввода времени для нового слота."""
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    day_date = data.get("adm_day_date")

    if not day_date:
        await message.answer("⚠️ Ошибка. Попробуйте заново через /admin.")
        await state.clear()
        return

    # Парсим время (одно или несколько)
    raw_times = message.text.strip().split(",")
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")
    added = []
    errors = []

    for raw in raw_times:
        t = raw.strip()
        if not time_pattern.match(t):
            errors.append(t)
            continue

        # Нормализация: 9:00 → 09:00
        parts = t.split(":")
        normalized = f"{int(parts[0]):02d}:{parts[1]}"

        # Проверка валидности
        h, m = int(parts[0]), int(parts[1])
        if h > 23 or m > 59:
            errors.append(t)
            continue

        # Убеждаемся, что рабочий день существует
        db.add_work_day(day_date)
        db.add_time_slot(day_date, normalized)
        added.append(normalized)

    response = ""
    if added:
        response += f"✅ Добавлены слоты: <b>{', '.join(added)}</b>\n"
    if errors:
        response += f"⚠️ Неверный формат: {', '.join(errors)}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Ещё слот", callback_data=f"adm_add_slot_{day_date}"
                )
            ],
            [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")],
        ]
    )

    await message.answer(response, reply_markup=kb, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("adm_del_slot_"))
async def cb_adm_del_slot(callback: CallbackQuery, state: FSMContext):
    """Удаление временного слота."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    # adm_del_slot_YYYY-MM-DD_HH:MM
    parts = callback.data.split("_", 4)  # adm, del, slot, date, time
    day_date = parts[3]
    slot_time = parts[4]

    db.remove_time_slot(day_date, slot_time)

    await callback.answer(f"🗑 Слот {slot_time} удалён")

    # Обновляем экран
    await show_slot_management(callback, day_date)


# ============================================================
# Просмотр расписания
# ============================================================


@router.callback_query(F.data == "adm_view_schedule")
async def cb_adm_view_schedule(callback: CallbackQuery, state: FSMContext):
    """Показываем календарь для выбора даты просмотра расписания."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    today = date.today()
    await state.set_state(AdminFSM.choosing_date)
    await state.update_data(adm_action="view_schedule")

    await callback.message.edit_text(
        "📅 <b>Выберите дату для просмотра расписания:</b>",
        reply_markup=generate_calendar(today.year, today.month, prefix="adm"),
        parse_mode="HTML",
    )
    await callback.answer()


async def show_schedule(callback: CallbackQuery, day_date: str):
    """Отображает полное расписание на выбранную дату."""
    slots = db.get_all_slots(day_date)

    text = f"📋 <b>Расписание на {day_date}:</b>\n\n"

    if not slots:
        text += "<i>На эту дату нет слотов.</i>"
    else:
        for s in slots:
            if s["client_name"]:
                svc = _service_name(s.get("service_id"))
                svc_label = f" | {svc}" if svc else ""
                text += (
                    f"🔴 <b>{s['slot_time']}</b> — {s['client_name']}{svc_label}\n"
                    f"    📱 {s['client_phone']}\n"
                )
            else:
                text += f"🟢 <b>{s['slot_time']}</b> — свободно\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ============================================================
# Закрытие дня
# ============================================================


@router.callback_query(F.data == "adm_close_day")
async def cb_adm_close_day(callback: CallbackQuery, state: FSMContext):
    """Открываем календарь для выбора дня для закрытия."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    today = date.today()
    await state.set_state(AdminFSM.choosing_date)
    await state.update_data(adm_action="close_day")

    await callback.message.edit_text(
        "📅 <b>Выберите дату для закрытия:</b>",
        reply_markup=generate_calendar(today.year, today.month, prefix="adm"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_confirm_close_"))
async def cb_adm_confirm_close(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение закрытия дня — удаляем рабочий день и всё связанное."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    day_date = callback.data.replace("adm_confirm_close_", "")

    # Получаем записи, чтобы уведомить клиентов
    bookings = db.get_bookings_for_date(day_date)

    # Удаляем рабочий день (CASCADE удалит слоты и записи)
    db.remove_work_day(day_date)

    # Уведомляем клиентов об отмене
    for b in bookings:
        try:
            await bot.send_message(
                b["user_id"],
                f"😔 <b>Ваша запись отменена</b>\n\n"
                f"Дата {day_date} закрыта мастером.\n"
                "Пожалуйста, запишитесь на другой день.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        # Удаляем напоминания
        try:
            from scheduler import remove_reminder

            remove_reminder(b["id"])
        except Exception:
            pass

    await callback.message.edit_text(
        f"✅ <b>День {day_date} закрыт.</b>\n\n"
        f"Удалено записей: {len(bookings)}\n"
        "Клиенты уведомлены.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")],
            ]
        ),
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ============================================================
# Отмена записи клиента (админом)
# ============================================================


@router.callback_query(F.data == "adm_cancel_booking")
async def cb_adm_cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Открываем календарь для выбора даты с записями."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    today = date.today()
    await state.set_state(AdminFSM.choosing_date)
    await state.update_data(adm_action="cancel_booking")

    await callback.message.edit_text(
        "📅 <b>Выберите дату для отмены записи:</b>",
        reply_markup=generate_calendar(today.year, today.month, prefix="adm"),
        parse_mode="HTML",
    )
    await callback.answer()


async def show_bookings_for_cancel(callback: CallbackQuery, day_date: str):
    """Показывает записи на дату с кнопками отмены."""
    bookings = db.get_bookings_for_date(day_date)

    if not bookings:
        await callback.message.edit_text(
            f"ℹ️ На <b>{day_date}</b> нет записей.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Админ-меню", callback_data="adm_menu"
                        )
                    ],
                ]
            ),
            parse_mode="HTML",
        )
        return

    text = f"📋 <b>Записи на {day_date}:</b>\n\n"
    buttons = []

    for b in bookings:
        svc = _service_name(b.get("service_id"))
        svc_label = f" | {svc}" if svc else ""
        text += (
            f"▸ {b['slot_time']} — {b['client_name']}{svc_label}\n"
            f"  📱 {b['client_phone']}\n\n"
        )
        btn_text = f"❌ {b['slot_time']} {b['client_name']}"
        if svc:
            btn_text += f" ({svc})"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"adm_do_cancel_{b['id']}",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")]
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_do_cancel_"))
async def cb_adm_do_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Админ отменяет конкретную запись."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    booking_id = int(callback.data.replace("adm_do_cancel_", ""))
    cancelled = db.cancel_booking_by_id(booking_id)

    if not cancelled:
        await callback.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    svc = _service_name(cancelled.get("service_id"))
    svc_line = f"\n💅 {svc}" if svc else ""

    # Уведомляем клиента
    try:
        await bot.send_message(
            cancelled["user_id"],
            f"😔 <b>Ваша запись отменена мастером</b>\n{svc_line}\n"
            f"📅 {cancelled['day_date']} в {cancelled['slot_time']}\n\n"
            "Пожалуйста, запишитесь на другое время.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Удаляем напоминание
    try:
        from scheduler import remove_reminder

        remove_reminder(booking_id)
    except Exception:
        pass

    svc_admin = f" ({svc})" if svc else ""
    await callback.message.edit_text(
        f"✅ Запись <b>{cancelled['client_name']}</b>{svc_admin} "
        f"на {cancelled['day_date']} {cancelled['slot_time']} отменена.\n"
        "Клиент уведомлён.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Админ-меню", callback_data="adm_menu")],
            ]
        ),
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer("✅ Запись отменена")
