# ============================================================
# database.py — Работа с SQLite: расписание и записи клиентов
#   Поддержка множественных записей одного пользователя
# ============================================================

import sqlite3
from datetime import date, datetime
from typing import Optional

from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Возвращает соединение с базой данных."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Создаёт таблицы при первом запуске."""
    conn = get_connection()
    cur = conn.cursor()

    # Рабочие дни мастера
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_days (
            day_date TEXT PRIMARY KEY           -- формат YYYY-MM-DD
        )
    """)

    # Временные слоты внутри рабочего дня
    cur.execute("""
        CREATE TABLE IF NOT EXISTS time_slots (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            day_date TEXT NOT NULL,              -- формат YYYY-MM-DD
            slot_time TEXT NOT NULL,             -- формат HH:MM
            UNIQUE(day_date, slot_time),
            FOREIGN KEY (day_date) REFERENCES work_days(day_date) ON DELETE CASCADE
        )
    """)

    # Записи клиентов (МНОЖЕСТВЕННЫЕ — без UNIQUE на user_id)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,       -- Telegram user ID
            slot_id      INTEGER NOT NULL UNIQUE, -- ссылка на time_slots.id (один слот = одна запись)
            service_id   TEXT NOT NULL,           -- ключ из SERVICES (config.py)
            client_name  TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE CASCADE
        )
    """)

    # Миграция: добавляем service_id, если таблица уже существовала без него
    try:
        cur.execute("ALTER TABLE bookings ADD COLUMN service_id TEXT NOT NULL DEFAULT 'french'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    conn.commit()
    conn.close()


# ============================================================
# Рабочие дни
# ============================================================

def add_work_day(day_date: str) -> bool:
    """Добавляет рабочий день. Возвращает True, если успешно."""
    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO work_days (day_date) VALUES (?)", (day_date,))
        conn.commit()
        return True
    finally:
        conn.close()


def remove_work_day(day_date: str) -> bool:
    """Удаляет рабочий день и все его слоты/записи (CASCADE)."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM work_days WHERE day_date = ?", (day_date,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_work_days_in_month(year: int, month: int) -> list[str]:
    """Возвращает список рабочих дней (YYYY-MM-DD) за указанный месяц."""
    prefix = f"{year:04d}-{month:02d}"
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT day_date FROM work_days WHERE day_date LIKE ? ORDER BY day_date",
            (f"{prefix}%",),
        ).fetchall()
        return [r["day_date"] for r in rows]
    finally:
        conn.close()


def is_work_day(day_date: str) -> bool:
    """Проверяет, является ли дата рабочим днём."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM work_days WHERE day_date = ?", (day_date,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ============================================================
# Временные слоты
# ============================================================

def add_time_slot(day_date: str, slot_time: str) -> bool:
    """Добавляет временной слот в рабочий день."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO time_slots (day_date, slot_time) VALUES (?, ?)",
            (day_date, slot_time),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_time_slot(day_date: str, slot_time: str) -> bool:
    """Удаляет временной слот (и связанную запись, если есть)."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM time_slots WHERE day_date = ? AND slot_time = ?",
            (day_date, slot_time),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_available_slots(day_date: str) -> list[dict]:
    """Возвращает свободные слоты на указанную дату."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT ts.id, ts.slot_time
            FROM time_slots ts
            LEFT JOIN bookings b ON b.slot_id = ts.id
            WHERE ts.day_date = ? AND b.id IS NULL
            ORDER BY ts.slot_time
            """,
            (day_date,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_slots(day_date: str) -> list[dict]:
    """Возвращает ВСЕ слоты на дату (занятые и свободные) — для админ-панели."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT ts.id, ts.slot_time,
                   b.client_name, b.client_phone, b.service_id,
                   b.user_id AS booked_user_id
            FROM time_slots ts
            LEFT JOIN bookings b ON b.slot_id = ts.id
            WHERE ts.day_date = ?
            ORDER BY ts.slot_time
            """,
            (day_date,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_slot_by_id(slot_id: int) -> Optional[dict]:
    """Возвращает информацию о слоте по его ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, day_date, slot_time FROM time_slots WHERE id = ?", (slot_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================
# Записи (бронирования) — МНОЖЕСТВЕННЫЕ
# ============================================================

def create_booking(
    user_id: int, slot_id: int, service_id: str, name: str, phone: str
) -> Optional[int]:
    """Создаёт запись клиента. Возвращает ID записи или None при ошибке."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO bookings (user_id, slot_id, service_id, client_name, client_phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, slot_id, service_id, name, phone),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_bookings_by_user(user_id: int) -> list[dict]:
    """Возвращает ВСЕ активные записи пользователя (может быть несколько)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT b.id, b.slot_id, b.service_id, b.client_name, b.client_phone,
                   ts.day_date, ts.slot_time
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.slot_id
            WHERE b.user_id = ?
            ORDER BY ts.day_date, ts.slot_time
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cancel_booking_by_id(booking_id: int) -> Optional[dict]:
    """Отменяет запись по ID. Возвращает данные удалённой записи."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT b.id, b.user_id, b.service_id, b.client_name, b.client_phone,
                   ts.day_date, ts.slot_time
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.slot_id
            WHERE b.id = ?
            """,
            (booking_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        return data
    finally:
        conn.close()


def has_active_booking(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя хотя бы одна активная запись."""
    return len(get_bookings_by_user(user_id)) > 0


def is_slot_booked_by_user(user_id: int, slot_id: int) -> bool:
    """Проверяет, не записан ли пользователь уже на этот конкретный слот."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM bookings WHERE user_id = ? AND slot_id = ?",
            (user_id, slot_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_bookings_for_date(day_date: str) -> list[dict]:
    """Возвращает все записи на указанную дату."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT b.id, b.user_id, b.service_id, b.client_name, b.client_phone,
                   ts.slot_time
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.slot_id
            WHERE ts.day_date = ?
            ORDER BY ts.slot_time
            """,
            (day_date,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_future_bookings() -> list[dict]:
    """Возвращает все будущие записи (для восстановления напоминаний)."""
    today = date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT b.id, b.user_id, b.service_id, b.client_name, b.client_phone,
                   ts.day_date, ts.slot_time
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.slot_id
            WHERE ts.day_date >= ?
            ORDER BY ts.day_date, ts.slot_time
            """,
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
