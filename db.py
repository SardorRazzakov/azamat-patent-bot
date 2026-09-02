import sqlite3
from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH, DEFAULT_DATES

# Статусы заявки
PENDING = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"

# Заявка занимает место, пока её не отменили
ACTIVE_STATUSES = (PENDING, CONFIRMED)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- ИНИЦИАЛИЗАЦИЯ ----------

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exam_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                seats_limit INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT,
                username TEXT,
                date_id INTEGER NOT NULL,
                passport_file_id TEXT,
                receipt_file_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                confirmed_by INTEGER,
                confirmed_by_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (date_id) REFERENCES exam_dates(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                booking_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                PRIMARY KEY (booking_id, admin_id)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings (date_id, status)"
        )
        # первичное заполнение датами
        cur = await db.execute("SELECT COUNT(*) FROM exam_dates")
        (count,) = await cur.fetchone()
        if count == 0:
            for i, title in enumerate(DEFAULT_DATES):
                await db.execute(
                    "INSERT INTO exam_dates (title, seats_limit, sort_order) VALUES (?, ?, ?)",
                    (title, 0, i),
                )
        await db.commit()
    print(f"[db] готова: {DB_PATH}")


# ---------- ДАТЫ: КЛИЕНТСКАЯ ЧАСТЬ ----------

async def get_bookable_dates() -> list[tuple[int, str]]:
    """Активные даты, на которых ещё есть места (seats_limit = 0 — без лимита)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT d.id, d.title
            FROM exam_dates d
            LEFT JOIN bookings b
                   ON b.date_id = d.id AND b.status IN ('pending', 'confirmed')
            WHERE d.is_active = 1
            GROUP BY d.id
            HAVING d.seats_limit = 0 OR COUNT(b.id) < d.seats_limit
            ORDER BY d.sort_order, d.id
            """
        )
        return await cur.fetchall()


async def is_date_bookable(date_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT d.seats_limit, COUNT(b.id)
            FROM exam_dates d
            LEFT JOIN bookings b
                   ON b.date_id = d.id AND b.status IN ('pending', 'confirmed')
            WHERE d.id = ? AND d.is_active = 1
            GROUP BY d.id
            """,
            (date_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        seats_limit, taken = row
        return seats_limit == 0 or taken < seats_limit


async def get_date_title(date_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT title FROM exam_dates WHERE id = ?", (date_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указана"


# ---------- ДАТЫ: АДМИНКА ----------

async def get_dates_overview() -> list[tuple]:
    """Все даты: (id, title, seats_limit, is_active, confirmed, pending)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT d.id, d.title, d.seats_limit, d.is_active,
                   COALESCE(SUM(b.status = 'confirmed'), 0),
                   COALESCE(SUM(b.status = 'pending'), 0)
            FROM exam_dates d
            LEFT JOIN bookings b ON b.date_id = d.id
            GROUP BY d.id
            ORDER BY d.sort_order, d.id
            """
        )
        return await cur.fetchall()


async def get_date_overview(date_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT d.id, d.title, d.seats_limit, d.is_active,
                   COALESCE(SUM(b.status = 'confirmed'), 0),
                   COALESCE(SUM(b.status = 'pending'), 0)
            FROM exam_dates d
            LEFT JOIN bookings b ON b.date_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (date_id,),
        )
        return await cur.fetchone()


async def add_date(title: str, seats_limit: int = 0) -> int | None:
    """Возвращает id новой даты или None, если такая дата уже есть."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM exam_dates")
        (sort_order,) = await cur.fetchone()
        try:
            cur = await db.execute(
                "INSERT INTO exam_dates (title, seats_limit, sort_order) VALUES (?, ?, ?)",
                (title, seats_limit, sort_order),
            )
        except sqlite3.IntegrityError:
            return None
        await db.commit()
        return cur.lastrowid


async def rename_date(date_id: int, title: str) -> str:
    """'ok' — переименована, 'duplicate' — название занято, 'missing' — даты нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cur = await db.execute(
                "UPDATE exam_dates SET title = ? WHERE id = ?", (title, date_id)
            )
        except sqlite3.IntegrityError:
            return "duplicate"
        await db.commit()
        return "ok" if cur.rowcount > 0 else "missing"


async def set_date_limit(date_id: int, seats_limit: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE exam_dates SET seats_limit = ? WHERE id = ?", (seats_limit, date_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_date(date_id: int) -> str:
    """Удаляет дату. Если по ней уже есть заявки — прячет её из списка ('archived')."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM bookings WHERE date_id = ?", (date_id,))
        (bookings_count,) = await cur.fetchone()
        if bookings_count:
            await db.execute("UPDATE exam_dates SET is_active = 0 WHERE id = ?", (date_id,))
            await db.commit()
            return "archived"
        await db.execute("DELETE FROM exam_dates WHERE id = ?", (date_id,))
        await db.commit()
        return "deleted"


async def restore_date(date_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE exam_dates SET is_active = 1 WHERE id = ?", (date_id,)
        )
        await db.commit()
        return cur.rowcount > 0


# ---------- ЗАЯВКИ ----------

async def has_active_booking(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM bookings WHERE user_id = ? AND status IN ('pending','confirmed')",
            (user_id,),
        )
        return await cur.fetchone() is not None


async def create_booking(
    user_id: int, full_name: str, username: str, date_id: int,
    passport_file_id: str, receipt_file_id: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO bookings
               (user_id, full_name, username, date_id, passport_file_id,
                receipt_file_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (user_id, full_name, username, date_id, passport_file_id,
             receipt_file_id, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_bookings_for_date(date_id: int) -> list[tuple]:
    """(id, full_name, username, user_id, status, confirmed_by_name, created_at)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT id, full_name, username, user_id, status,
                      confirmed_by_name, created_at
               FROM bookings
               WHERE date_id = ?
               ORDER BY created_at, id""",
            (date_id,),
        )
        return await cur.fetchall()


async def get_booking(booking_id: int) -> tuple | None:
    """(id, user_id, full_name, username, date_id, status, confirmed_by_name,
        created_at, date_title)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.id, b.user_id, b.full_name, b.username, b.date_id, b.status,
                      b.confirmed_by_name, b.created_at, d.title
               FROM bookings b
               LEFT JOIN exam_dates d ON d.id = b.date_id
               WHERE b.id = ?""",
            (booking_id,),
        )
        return await cur.fetchone()


async def cancel_booking(booking_id: int) -> tuple[bool, int | None]:
    """Возвращает (была ли отменена сейчас, user_id клиента)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status != 'cancelled'",
            (booking_id,),
        )
        await db.commit()
        changed = cur.rowcount > 0

        cur = await db.execute("SELECT user_id FROM bookings WHERE id = ?", (booking_id,))
        row = await cur.fetchone()
        return changed, (row[0] if row else None)


async def claim_booking(booking_id: int, admin_id: int, admin_name: str):
    """Возвращает (успех, user_id, имя_подтвердившего)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE bookings
               SET status = 'confirmed', confirmed_by = ?, confirmed_by_name = ?
               WHERE id = ? AND status = 'pending'""",
            (admin_id, admin_name, booking_id),
        )
        await db.commit()
        won = cur.rowcount > 0

        cur = await db.execute(
            "SELECT user_id, confirmed_by_name FROM bookings WHERE id = ?",
            (booking_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False, None, None
        return won, row[0], row[1]


# ---------- СООБЩЕНИЯ АДМИНАМ ----------

async def save_admin_message(booking_id: int, admin_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admin_messages VALUES (?, ?, ?)",
            (booking_id, admin_id, message_id),
        )
        await db.commit()


async def get_admin_messages(booking_id: int) -> list[tuple[int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT admin_id, message_id FROM admin_messages WHERE booking_id = ?",
            (booking_id,),
        )
        return await cur.fetchall()


# ---------- СТАТИСТИКА И ЭКСПОРТ ----------

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT status, COUNT(*) FROM bookings GROUP BY status")
        by_status = {status: count for status, count in await cur.fetchall()}

        cur = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(is_active), 0) FROM exam_dates"
        )
        dates_total, dates_active = await cur.fetchone()

    return {
        "confirmed": by_status.get(CONFIRMED, 0),
        "pending": by_status.get(PENDING, 0),
        "cancelled": by_status.get(CANCELLED, 0),
        "total": sum(by_status.values()),
        "dates_total": dates_total,
        "dates_active": dates_active,
    }


async def get_export_rows() -> list[tuple]:
    """(id, date_title, full_name, username, user_id, status, confirmed_by_name, created_at)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.id, d.title, b.full_name, b.username, b.user_id,
                      b.status, b.confirmed_by_name, b.created_at
               FROM bookings b
               LEFT JOIN exam_dates d ON d.id = b.date_id
               ORDER BY d.sort_order, d.id, b.created_at, b.id"""
        )
        return await cur.fetchall()
