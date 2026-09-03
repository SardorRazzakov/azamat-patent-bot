import sqlite3
from datetime import date, datetime, time, timedelta, timezone

import aiosqlite

from config import DB_PATH, DEFAULT_DATES, TZ

# Статусы заявки
PENDING = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"

# Заявка занимает место, пока её не отменили
ACTIVE_STATUSES = (PENDING, CONFIRMED)

# Итог экзамена, проставляется админом после даты
PASSED = "passed"
FAILED = "failed"
NO_SHOW = "no_show"
OUTCOMES = (PASSED, FAILED, NO_SHOW)

# Шаги воронки — по одному событию на шаг, порядок важен для отчёта
STEP_START = "start"
STEP_LANG = "lang"
STEP_DATE = "date"
STEP_PASSPORT = "passport"
STEP_RECEIPT = "receipt"
STEP_PAID = "paid"
STEP_OUTCOME = "outcome"
FUNNEL_STEPS = (
    (STEP_START, "Запустили бота"),
    (STEP_LANG, "Выбрали язык"),
    (STEP_DATE, "Выбрали дату"),
    (STEP_PASSPORT, "Прислали паспорт"),
    (STEP_RECEIPT, "Прислали чек"),
    (STEP_PAID, "Оплата подтверждена"),
    (STEP_OUTCOME, "Результат проставлен"),
)


# Принимаем 07.09.2026, 7.9.26, 07.09 (текущий год), 2026-09-07.
_DATE_PATTERNS = ("%d.%m.%Y", "%d.%m.%y", "%d.%m", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_exam_date(raw: str) -> str | None:
    """Текст -> 'YYYY-MM-DD'. None, если не дата или такого числа нет
    в календаре (например, 31 сентября)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for pattern in _DATE_PATTERNS:
        try:
            dt = datetime.strptime(raw, pattern)
        except ValueError:
            continue
        if "%Y" not in pattern and "%y" not in pattern:
            dt = dt.replace(year=today().year)
        return dt.date().isoformat()
    return None


def today() -> date:
    """Сегодня по Ташкенту: в UTC дата переключается на 5 часов позже,
    и вечером экзамен пропадал бы из записи на день раньше срока."""
    return datetime.now(TZ).date()


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
                sort_order INTEGER NOT NULL DEFAULT 0,
                exam_date TEXT
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
                reminder_sent_at TEXT,
                outcome TEXT,
                outcome_at TEXT,
                outcome_by INTEGER,
                outcome_by_name TEXT,
                applicant_name TEXT,
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                step TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fsm_storage (
                key TEXT PRIMARY KEY,
                state TEXT,
                data TEXT NOT NULL DEFAULT '{}'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings (date_id, status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_step ON events (step, created_at)"
        )
        # колонки появились позже таблицы — досоздаём в уже существующих базах
        cur = await db.execute("PRAGMA table_info(bookings)")
        columns = {row[1] for row in await cur.fetchall()}
        for column, kind in (
            ("cancelled_by", "INTEGER"),
            ("cancelled_by_name", "TEXT"),
            ("reminder_sent_at", "TEXT"),
            ("outcome", "TEXT"),
            ("outcome_at", "TEXT"),
            ("outcome_by", "INTEGER"),
            ("outcome_by_name", "TEXT"),
            ("applicant_name", "TEXT"),
        ):
            if column not in columns:
                await db.execute(f"ALTER TABLE bookings ADD COLUMN {column} {kind}")
                print(f"[db] добавлена колонка bookings.{column}")

        cur = await db.execute("PRAGMA table_info(exam_dates)")
        if "exam_date" not in {row[1] for row in await cur.fetchall()}:
            await db.execute("ALTER TABLE exam_dates ADD COLUMN exam_date TEXT")
            print("[db] добавлена колонка exam_dates.exam_date")
            # у дат вида 07.09.2026 число вытаскивается из названия;
            # «15 sentabr» и прочий свободный текст остаётся без даты
            cur = await db.execute("SELECT id, title FROM exam_dates")
            filled = 0
            for date_id, title in await cur.fetchall():
                iso = parse_exam_date(title)
                if iso:
                    await db.execute(
                        "UPDATE exam_dates SET exam_date = ? WHERE id = ?", (iso, date_id)
                    )
                    filled += 1
            print(f"[db] дата распознана у {filled} записей из названия")

        # первичное заполнение датами
        cur = await db.execute("SELECT COUNT(*) FROM exam_dates")
        (count,) = await cur.fetchone()
        if count == 0:
            for i, (title, seats_limit) in enumerate(DEFAULT_DATES):
                await db.execute(
                    """INSERT INTO exam_dates (title, seats_limit, sort_order, exam_date)
                       VALUES (?, ?, ?, ?)""",
                    (title, seats_limit, i, parse_exam_date(title)),
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
              AND (d.exam_date IS NULL OR d.exam_date >= ?)
            GROUP BY d.id
            HAVING d.seats_limit = 0 OR COUNT(b.id) < d.seats_limit
            ORDER BY d.exam_date IS NULL, d.exam_date, d.sort_order, d.id
            """,
            (today().isoformat(),),
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
              AND (d.exam_date IS NULL OR d.exam_date >= ?)
            GROUP BY d.id
            """,
            (date_id, today().isoformat()),
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
                   COALESCE(SUM(b.status = 'pending'), 0),
                   d.exam_date
            FROM exam_dates d
            LEFT JOIN bookings b ON b.date_id = d.id
            GROUP BY d.id
            ORDER BY d.exam_date IS NULL, d.exam_date, d.sort_order, d.id
            """
        )
        return await cur.fetchall()


async def get_date_overview(date_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT d.id, d.title, d.seats_limit, d.is_active,
                   COALESCE(SUM(b.status = 'confirmed'), 0),
                   COALESCE(SUM(b.status = 'pending'), 0),
                   d.exam_date
            FROM exam_dates d
            LEFT JOIN bookings b ON b.date_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (date_id,),
        )
        return await cur.fetchone()


async def add_date(title: str, seats_limit: int = 0,
                   exam_date: str | None = None) -> int | None:
    """Возвращает id новой даты или None, если такая дата уже есть."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM exam_dates")
        (sort_order,) = await cur.fetchone()
        try:
            cur = await db.execute(
                """INSERT INTO exam_dates (title, seats_limit, sort_order, exam_date)
                   VALUES (?, ?, ?, ?)""",
                (title, seats_limit, sort_order, exam_date),
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


async def set_exam_date(date_id: int, exam_date: str | None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE exam_dates SET exam_date = ? WHERE id = ?", (exam_date, date_id)
        )
        await db.commit()
        return cur.rowcount > 0


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


# ---------- ИТОГ ЭКЗАМЕНА ----------

async def set_outcome(booking_id: int, outcome: str,
                      admin_id: int, admin_name: str) -> bool:
    """Проставляет итог. Переставить можно — пишем последнего, кто трогал."""
    if outcome not in OUTCOMES:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE bookings
               SET outcome = ?, outcome_at = ?, outcome_by = ?, outcome_by_name = ?
               WHERE id = ? AND status = ?""",
            (outcome, _now(), admin_id, admin_name, booking_id, CONFIRMED),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_outcome_stats() -> dict:
    """Итоги по экзаменам, которые уже прошли (подтверждённые заявки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.outcome, COUNT(*)
               FROM bookings b
               JOIN exam_dates d ON d.id = b.date_id
               WHERE b.status = ? AND d.exam_date IS NOT NULL AND d.exam_date < ?
               GROUP BY b.outcome""",
            (CONFIRMED, today().isoformat()),
        )
        by_outcome = {row[0]: row[1] for row in await cur.fetchall()}

    passed = by_outcome.get(PASSED, 0)
    failed = by_outcome.get(FAILED, 0)
    no_show = by_outcome.get(NO_SHOW, 0)
    marked = passed + failed + no_show
    return {
        "passed": passed,
        "failed": failed,
        "no_show": no_show,
        "came": passed + failed,
        "marked": marked,
        "unmarked": by_outcome.get(None, 0),
        "total": marked + by_outcome.get(None, 0),
        # доля неявок считается от проставленных, иначе она врёт,
        # пока часть заявок ещё без итога
        "no_show_pct": round(no_show * 100 / marked) if marked else 0,
    }


# ---------- ВОРОНКА ----------

async def log_event(user_id: int, step: str):
    """Одно событие на шаг. Ошибку логирования глотаем: воронка не должна
    ронять диалог с клиентом."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO events (user_id, step, created_at) VALUES (?, ?, ?)",
                (user_id, step, _now()),
            )
            await db.commit()
    except Exception as e:
        print(f"[events] не записал {step} для {user_id}: {e}")


def period_start(period: str) -> str:
    """Граница периода в UTC, отсчитанная от полуночи по Ташкенту."""
    days = {"today": 0, "week": 6, "month": 29}.get(period, 0)
    start = datetime.combine(today() - timedelta(days=days), time.min, tzinfo=TZ)
    return start.astimezone(timezone.utc).isoformat()


async def get_funnel(period: str) -> list[tuple[str, str, int]]:
    """[(step, подпись, сколько РАЗНЫХ человек дошло)] в порядке шагов."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT step, COUNT(DISTINCT user_id) FROM events
               WHERE created_at >= ? GROUP BY step""",
            (period_start(period),),
        )
        counts = {step: n for step, n in await cur.fetchall()}
    return [(step, label, counts.get(step, 0)) for step, label in FUNNEL_STEPS]


# ---------- НАПОМИНАНИЯ ----------

async def get_bookings_to_remind(exam_date: str) -> list[tuple]:
    """Подтверждённые заявки на дату exam_date, которым ещё не напоминали.
    Возвращает (booking_id, user_id, date_title)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.id, b.user_id, d.title
               FROM bookings b
               JOIN exam_dates d ON d.id = b.date_id
               WHERE b.status = ?
                 AND d.exam_date = ?
                 AND b.reminder_sent_at IS NULL""",
            (CONFIRMED, exam_date),
        )
        return await cur.fetchall()


async def mark_reminded(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET reminder_sent_at = ? WHERE id = ?",
            (_now(), booking_id),
        )
        await db.commit()


# ---------- ЯЗЫК КЛИЕНТА ----------

async def get_user_lang(user_id: int) -> str | None:
    """None — клиент ещё не выбирал язык."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, lang, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   lang = excluded.lang, updated_at = excluded.updated_at""",
            (user_id, lang, _now()),
        )
        await db.commit()


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
    applicant_name: str | None = None,
) -> int | None:
    """None — на дате не осталось мест или её удалили.

    Проверка лимита и вставка идут в одной транзакции: иначе двое клиентов
    успевают пройти is_date_bookable() и оба занимают последнее место.
    """
    async with aiosqlite.connect(DB_PATH, isolation_level=None) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cur = await db.execute(
                "SELECT seats_limit FROM exam_dates WHERE id = ? AND is_active = 1",
                (date_id,),
            )
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None

            seats_limit = row[0]
            if seats_limit:
                cur = await db.execute(
                    """SELECT COUNT(*) FROM bookings
                       WHERE date_id = ? AND status IN (?, ?)""",
                    (date_id, PENDING, CONFIRMED),
                )
                (taken,) = await cur.fetchone()
                if taken >= seats_limit:
                    await db.execute("ROLLBACK")
                    return None

            cur = await db.execute(
                """INSERT INTO bookings
                   (user_id, full_name, username, date_id, passport_file_id,
                    receipt_file_id, status, created_at, applicant_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, full_name, username, date_id, passport_file_id,
                 receipt_file_id, PENDING, _now(), applicant_name),
            )
            booking_id = cur.lastrowid
            await db.execute("COMMIT")
            return booking_id
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def get_bookings_for_date(date_id: int) -> list[tuple]:
    """(id, full_name, username, user_id, status, confirmed_by_name, created_at,
        outcome, applicant_name)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT id, full_name, username, user_id, status,
                      confirmed_by_name, created_at, outcome, applicant_name
               FROM bookings
               WHERE date_id = ?
               ORDER BY created_at, id""",
            (date_id,),
        )
        return await cur.fetchall()


async def get_booking(booking_id: int) -> tuple | None:
    """(id, user_id, full_name, username, date_id, status, confirmed_by_name,
        created_at, date_title, passport_file_id, receipt_file_id,
        cancelled_by_name, exam_date, outcome, outcome_by_name, outcome_at,
        applicant_name).

    Новые поля добавлены в конец, чтобы не ломать распаковку по индексам.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.id, b.user_id, b.full_name, b.username, b.date_id, b.status,
                      b.confirmed_by_name, b.created_at, d.title,
                      b.passport_file_id, b.receipt_file_id, b.cancelled_by_name,
                      d.exam_date, b.outcome, b.outcome_by_name, b.outcome_at,
                      b.applicant_name
               FROM bookings b
               LEFT JOIN exam_dates d ON d.id = b.date_id
               WHERE b.id = ?""",
            (booking_id,),
        )
        return await cur.fetchone()


async def cancel_booking(
    booking_id: int, admin_id: int, admin_name: str
) -> tuple[bool, int | None]:
    """Возвращает (была ли отменена сейчас, user_id клиента)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE bookings
               SET status = ?, cancelled_by = ?, cancelled_by_name = ?
               WHERE id = ? AND status != ?""",
            (CANCELLED, admin_id, admin_name, booking_id, CANCELLED),
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
    """(id, date_title, full_name, username, user_id, status, confirmed_by_name,
        created_at, applicant_name, outcome)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT b.id, d.title, b.full_name, b.username, b.user_id,
                      b.status, b.confirmed_by_name, b.created_at,
                      b.applicant_name, b.outcome
               FROM bookings b
               LEFT JOIN exam_dates d ON d.id = b.date_id
               ORDER BY d.exam_date IS NULL, d.exam_date, d.sort_order,
                        d.id, b.created_at, b.id"""
        )
        return await cur.fetchall()
