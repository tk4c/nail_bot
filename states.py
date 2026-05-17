# ============================================================
# states.py — FSM-состояния для записи клиента и админ-панели
# ============================================================

from aiogram.fsm.state import State, StatesGroup


class BookingFSM(StatesGroup):
    """Машина состояний для процесса записи."""
    choosing_service = State()    # Пользователь выбирает услугу
    choosing_date = State()       # Пользователь выбирает дату
    choosing_time = State()       # Пользователь выбирает время
    entering_name = State()       # Пользователь вводит имя
    entering_phone = State()      # Пользователь вводит телефон
    confirming = State()          # Пользователь подтверждает запись


class AdminFSM(StatesGroup):
    """Машина состояний для админ-панели."""
    choosing_action = State()       # Выбор действия в админ-панели
    choosing_date = State()         # Выбор даты в админском календаре
    adding_slot_time = State()      # Ввод времени для нового слота
    viewing_schedule = State()      # Просмотр расписания на дату
