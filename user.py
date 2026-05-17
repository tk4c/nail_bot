# ============================================================
# handlers/user.py — Пользовательские хэндлеры
#   • Главное меню
#   • Запись (FSM): услуга → дата → время → имя → телефон → подтверждение
#   • Отмена конкретной записи (поддержка нескольких)
#   • Мои записи
#   • Прайс-лист
#   • Портфолио
# ============================================================

from datetime import date, datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import database as db
from config import (
    ADMIN_ID,
    SCHEDULE_CHANNEL_ID,
    SERVICES,
    PRICE_TEXT,
    PORTFOLIO_TEXT,
    PORTFOLIO_URL,
    REMINDER_HOURS_BEFORE,
)
from states import BookingFSM
from calendar_kb import generate_calendar, get_prev_month, get_next_month
from handlers.subscription import is_subscribed, subscription_keyboard

router = Router()


# ============================================================
# Вспомогательная функция: название услуги по ID
# ============================================================

def service_name(service_id: str) -> str:
    """Возвращает человекопонятное название услуги."""
    svc = SERVICES.get(service_id)
    return svc["name"] if svc else service_id


def service_price(service_id: str) -> int:
    """Возвращает цену услуги."""
    svc = SERVICES.get(service_id)
    return svc["price"] if svc else 0


# ============================================================
# Главное меню
# ============================================================

def main_menu_kb() -> InlineKeyboardMarkup:
    """Клавиатура главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="book_start")],
        [InlineKeyboardButton(text="📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton(text="💰 Прайсы", callback_data="show_prices")],
        [InlineKeyboardButton(text="📸 Портфолио", callback_data="show_portfolio")],
    ])


WELCOME_TEXT = (
    "💅 <b>Добро пожаловать!</b>\n\n"
    "Я бот для записи к мастеру маникюра.\n"
    "Выберите действие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start — показываем главное меню."""
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню."""
    await state.clear()
    await callback.message.edit_text(
        WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# Прайс-лист (без FSM)
# ============================================================

@router.callback_query(F.data == "show_prices")
async def cb_show_prices(callback: CallbackQuery):
    """Показывает прайс-лист."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])
    await callback.message.edit_text(PRICE_TEXT, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ============================================================
# Портфолио (без FSM)
# ============================================================

@router.callback_query(F.data == "show_portfolio")
async def cb_show_portfolio(callback: CallbackQuery):
    """Показывает кнопку со ссылкой на портфолио."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Смотреть портфолио", url=PORTFOLIO_URL)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])
    await callback.message.edit_text(PORTFOLIO_TEXT, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ============================================================
# Мои записи — просмотр и отмена конкретной
# ============================================================

@router.callback_query(F.data == "my_bookings")
async def cb_my_bookings(callback: CallbackQuery, state: FSMContext):
    """Показывает все записи пользователя с кнопками отмены."""
    await state.clear()
    user_id = callback.from_user.id
    bookings = db.get_bookings_by_user(user_id)

    if not bookings:
        await callback.message.edit_text(
            "ℹ️ У вас нет активных записей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Записаться", callback_data="book_start")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
            ]),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = "📋 <b>Ваши записи:</b>\n\n"
    buttons = []

    for i, b in enumerate(bookings, 1):
        svc = service_name(b["service_id"])
        text += (
            f"<b>{i}.</b> {svc}\n"
            f"    📅 {b['day_date']}  🕐 {b['slot_time']}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ Отменить: {svc} ({b['day_date']} {b['slot_time']})",
                callback_data=f"cancel_{b['id']}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Отмена конкретной записи
# ============================================================

@router.callback_query(F.data.startswith("cancel_"))
async def cb_cancel_specific(callback: CallbackQuery, state: FSMContext):
    """Показывает подтверждение отмены конкретной записи."""
    booking_id = int(callback.data.replace("cancel_", ""))
    user_id = callback.from_user.id

    # Проверяем, что запись принадлежит этому пользователю
    bookings = db.get_bookings_by_user(user_id)
    booking = next((b for b in bookings if b["id"] == booking_id), None)

    if not booking:
        await callback.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    svc = service_name(booking["service_id"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}"),
            InlineKeyboardButton(text="🔙 Нет", callback_data="my_bookings"),
        ],
    ])

    await callback.message.edit_text(
        f"❓ <b>Отменить запись?</b>\n\n"
        f"💅 Услуга: <b>{svc}</b>\n"
        f"📅 Дата: <b>{booking['day_date']}</b>\n"
        f"🕐 Время: <b>{booking['slot_time']}</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel_"))
async def cb_confirm_cancel(callback: CallbackQuery, bot: Bot):
    """Подтверждение отмены записи — удаляем из БД."""
    booking_id = int(callback.data.replace("confirm_cancel_", ""))
    user_id = callback.from_user.id

    # Безопасность: проверяем принадлежность записи
    bookings = db.get_bookings_by_user(user_id)
    if not any(b["id"] == booking_id for b in bookings):
        await callback.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    cancelled = db.cancel_booking_by_id(booking_id)

    if not cancelled:
        await callback.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    svc = service_name(cancelled["service_id"])

    await callback.message.edit_text(
        f"✅ <b>Запись отменена</b>\n\n"
        f"💅 {svc}\n"
        f"📅 {cancelled['day_date']} в {cancelled['slot_time']}\n\n"
        "Слот снова доступен для записи.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться", callback_data="book_start")],
            [InlineKeyboardButton(text="📋 Мои записи", callback_data="my_bookings")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
        ]),
        parse_mode="HTML",
    )

    # Удаляем запланированное напоминание
    try:
        from scheduler import remove_reminder
        remove_reminder(booking_id)
    except Exception:
        pass

    # Уведомляем админа об отмене
    admin_text = (
        "🔕 <b>Запись отменена клиентом</b>\n\n"
        f"💅 {svc}\n"
        f"👤 {cancelled['client_name']}\n"
        f"📅 {cancelled['day_date']} в {cancelled['slot_time']}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("✅ Запись отменена")


# ============================================================
# Запись — Шаг 1: Проверка подписки → выбор услуги
# ============================================================

@router.callback_query(F.data == "book_start")
async def cb_book_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало записи: проверяем подписку, показываем выбор услуги."""
    user_id = callback.from_user.id

    # Проверка подписки на канал
    if not await is_subscribed(bot, user_id):
        await callback.message.edit_text(
            "⚠️ <b>Для записи необходимо подписаться на канал</b>",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Показываем выбор услуги
    await state.set_state(BookingFSM.choosing_service)

    buttons = []
    for svc_id, svc_data in SERVICES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"💅 {svc_data['name']} — {svc_data['price']:,} ₽",
                callback_data=f"svc_{svc_id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    await callback.message.edit_text(
        "💅 <b>Выберите услугу:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Проверка подписки (кнопка «Проверить подписку»)
# ============================================================

@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot):
    """Повторная проверка подписки."""
    if await is_subscribed(bot, callback.from_user.id):
        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\nТеперь вы можете записаться.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    else:
        await callback.answer("❌ Вы ещё не подписаны на канал.", show_alert=True)


# ============================================================
# Запись — Шаг 2: Выбор услуги → календарь
# ============================================================

@router.callback_query(F.data.startswith("svc_"), BookingFSM.choosing_service)
async def cb_choose_service(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал услугу — показываем календарь."""
    service_id = callback.data.replace("svc_", "")

    if service_id not in SERVICES:
        await callback.answer("⚠️ Услуга не найдена.", show_alert=True)
        return

    await state.update_data(service_id=service_id)
    await state.set_state(BookingFSM.choosing_date)

    svc = SERVICES[service_id]
    today = date.today()

    await callback.message.edit_text(
        f"💅 Услуга: <b>{svc['name']} — {svc['price']:,} ₽</b>\n\n"
        "📅 <b>Выберите дату</b>\n"
        "✅ — доступные дни для записи",
        reply_markup=generate_calendar(today.year, today.month, prefix="cal"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Запись — Навигация по календарю
# ============================================================

@router.callback_query(F.data.startswith("cal_prev_"))
async def cb_cal_prev(callback: CallbackQuery):
    """Переход на предыдущий месяц."""
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    new_year, new_month = get_prev_month(year, month)
    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar(new_year, new_month, prefix="cal")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cal_next_"))
async def cb_cal_next(callback: CallbackQuery):
    """Переход на следующий месяц."""
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    new_year, new_month = get_next_month(year, month)
    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar(new_year, new_month, prefix="cal")
    )
    await callback.answer()


# ============================================================
# Запись — Шаг 3: Выбор даты → показать слоты
# ============================================================

@router.callback_query(F.data.startswith("cal_day_"))
async def cb_cal_day(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал дату — показываем свободные слоты."""
    day_date = callback.data.replace("cal_day_", "")
    slots = db.get_available_slots(day_date)

    if not slots:
        await callback.answer("😔 На эту дату нет свободных слотов.", show_alert=True)
        return

    # Сохраняем выбранную дату в FSM
    await state.update_data(day_date=day_date)
    await state.set_state(BookingFSM.choosing_time)

    data = await state.get_data()
    svc = SERVICES.get(data.get("service_id", ""), {})

    # Формируем кнопки со слотами
    buttons = []
    for slot in slots:
        buttons.append([
            InlineKeyboardButton(
                text=f"🕐 {slot['slot_time']}",
                callback_data=f"slot_{slot['id']}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к календарю", callback_data="back_to_calendar")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"💅 Услуга: <b>{svc.get('name', '')}</b>\n"
        f"📅 Дата: <b>{day_date}</b>\n\n"
        "Выберите время:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_calendar")
async def cb_back_to_calendar(callback: CallbackQuery, state: FSMContext):
    """Возврат к календарю с сохранением выбранной услуги."""
    data = await state.get_data()
    svc_id = data.get("service_id", "")
    svc = SERVICES.get(svc_id, {})

    await state.set_state(BookingFSM.choosing_date)
    today = date.today()

    await callback.message.edit_text(
        f"💅 Услуга: <b>{svc.get('name', '')} — {svc.get('price', 0):,} ₽</b>\n\n"
        "📅 <b>Выберите дату</b>\n"
        "✅ — доступные дни для записи",
        reply_markup=generate_calendar(today.year, today.month, prefix="cal"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Запись — Шаг 4: Выбор времени → запрос имени
# ============================================================

@router.callback_query(F.data.startswith("slot_"), BookingFSM.choosing_time)
async def cb_slot_select(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал временной слот — запрашиваем имя."""
    slot_id = int(callback.data.replace("slot_", ""))
    slot = db.get_slot_by_id(slot_id)

    if not slot:
        await callback.answer("⚠️ Слот не найден.", show_alert=True)
        return

    data = await state.get_data()
    svc = SERVICES.get(data.get("service_id", ""), {})

    await state.update_data(slot_id=slot_id, slot_time=slot["slot_time"])
    await state.set_state(BookingFSM.entering_name)

    await callback.message.edit_text(
        f"💅 Услуга: <b>{svc.get('name', '')}</b>\n"
        f"📅 Дата: <b>{slot['day_date']}</b>\n"
        f"🕐 Время: <b>{slot['slot_time']}</b>\n\n"
        "✏️ Введите ваше <b>имя</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# Запись — Шаг 5: Ввод имени → запрос телефона
# ============================================================

@router.message(BookingFSM.entering_name)
async def msg_enter_name(message: Message, state: FSMContext):
    """Получили имя — запрашиваем телефон."""
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("⚠️ Введите корректное имя (от 2 до 50 символов).")
        return

    await state.update_data(client_name=name)
    await state.set_state(BookingFSM.entering_phone)

    await message.answer(
        f"👤 Имя: <b>{name}</b>\n\n"
        "📱 Введите ваш <b>номер телефона</b>:",
        parse_mode="HTML",
    )


# ============================================================
# Запись — Шаг 6: Ввод телефона → подтверждение
# ============================================================

@router.message(BookingFSM.entering_phone)
async def msg_enter_phone(message: Message, state: FSMContext):
    """Получили телефон — показываем данные для подтверждения."""
    phone = message.text.strip()

    # Простая валидация номера
    phone_digits = "".join(c for c in phone if c.isdigit())
    if len(phone_digits) < 10 or len(phone_digits) > 15:
        await message.answer("⚠️ Введите корректный номер телефона.")
        return

    await state.update_data(client_phone=phone)
    data = await state.get_data()

    svc = SERVICES.get(data.get("service_id", ""), {})

    await state.set_state(BookingFSM.confirming)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="main_menu"),
        ],
    ])

    await message.answer(
        "📋 <b>Проверьте данные записи:</b>\n\n"
        f"💅 Услуга: <b>{svc.get('name', '')}</b>\n"
        f"💰 Стоимость: <b>{svc.get('price', 0):,} ₽</b>\n"
        f"📅 Дата: <b>{data['day_date']}</b>\n"
        f"🕐 Время: <b>{data['slot_time']}</b>\n"
        f"👤 Имя: <b>{data['client_name']}</b>\n"
        f"📱 Телефон: <b>{phone}</b>\n\n"
        "Всё верно?",
        reply_markup=kb,
        parse_mode="HTML",
    )


# ============================================================
# Запись — Шаг 7: Подтверждение → сохранение
# ============================================================

@router.callback_query(F.data == "confirm_booking", BookingFSM.confirming)
async def cb_confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение записи — сохраняем в БД, уведомляем админа и канал."""
    data = await state.get_data()
    user_id = callback.from_user.id
    svc = SERVICES.get(data.get("service_id", ""), {})

    # Создаём запись
    booking_id = db.create_booking(
        user_id=user_id,
        slot_id=data["slot_id"],
        service_id=data["service_id"],
        name=data["client_name"],
        phone=data["client_phone"],
    )

    if not booking_id:
        await callback.message.edit_text(
            "😔 К сожалению, этот слот уже занят. Попробуйте выбрать другое время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Выбрать другое время", callback_data="book_start")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
            ]),
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    await state.clear()

    # Сообщение пользователю
    await callback.message.edit_text(
        "✅ <b>Вы успешно записаны!</b>\n\n"
        f"💅 Услуга: <b>{svc.get('name', '')}</b>\n"
        f"📅 Дата: <b>{data['day_date']}</b>\n"
        f"🕐 Время: <b>{data['slot_time']}</b>\n\n"
        "Вы можете записаться ещё на другую услугу\n"
        "или просмотреть все записи.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться ещё", callback_data="book_start")],
            [InlineKeyboardButton(text="📋 Мои записи", callback_data="my_bookings")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
        ]),
        parse_mode="HTML",
    )

    # Уведомляем администратора
    admin_text = (
        "🔔 <b>Новая запись!</b>\n\n"
        f"💅 Услуга: <b>{svc.get('name', '')}</b>\n"
        f"👤 Имя: <b>{data['client_name']}</b>\n"
        f"📱 Телефон: <b>{data['client_phone']}</b>\n"
        f"📅 Дата: <b>{data['day_date']}</b>\n"
        f"🕐 Время: <b>{data['slot_time']}</b>\n"
        f"🆔 Telegram ID: <code>{user_id}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception:
        pass

    # Публикуем в канал с расписанием
    channel_text = (
        "📋 <b>Новая запись</b>\n\n"
        f"💅 {svc.get('name', '')}\n"
        f"📅 {data['day_date']} в {data['slot_time']}\n"
        f"👤 {data['client_name']}"
    )
    try:
        await bot.send_message(SCHEDULE_CHANNEL_ID, channel_text, parse_mode="HTML")
    except Exception:
        pass

    # Планируем напоминание через APScheduler
    try:
        from scheduler import schedule_reminder
        await schedule_reminder(bot, user_id, data["day_date"], data["slot_time"], booking_id)
    except Exception:
        pass

    await callback.answer("✅ Запись подтверждена!")


# ============================================================
# Игнорируем нажатия на пустые кнопки календаря
# ============================================================

@router.callback_query(F.data == "ignore")
async def cb_ignore(callback: CallbackQuery):
    """Нажатие на неактивную кнопку — ничего не делаем."""
    await callback.answer()
