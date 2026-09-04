import asyncio
import sqlite3
from contextlib import asynccontextmanager
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


# ---------- СОЕДИНЕНИЕ ----------
# Одно долгоживущее соединение на процесс вместо нового на каждый запрос:
# реплика одна, а открытие файла и разбор схемы на каждый чих — самая
# дорогая часть при сотнях пользователей.

def _pylower(value):
    return value.lower() if isinstance(value, str) else value


_conn: aiosqlite.Connection | None = None
_conn_lock = asyncio.Lock()

# Транзакции create_booking() идут через тот же коннект, что и остальные
# запросы, поэтому их надо развести явно — иначе чужая вставка попадёт
# внутрь чужого BEGIN IMMEDIATE.
_tx_lock = asyncio.Lock()


async def connect() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        async with _conn_lock:
            if _conn is None:                       # проверка после ожидания
                conn = aiosqlite.connect(DB_PATH, isolation_level=None)
                # поток соединения не должен держать процесс живым, если
                # close() забыли вызвать — иначе скрипт не завершится
                conn.daemon = True
                conn = await conn
                # WAL: читатели не блокируют писателя и наоборот.
                await conn.execute("PRAGMA journal_mode=WAL")
                # Ждать освободившуюся блокировку, а не падать сразу.
                await conn.execute("PRAGMA busy_timeout=5000")
                # NORMAL достаточно: при WAL потеряется максимум последняя
                # транзакция и только при аварии самой машины.
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA foreign_keys=ON")
                # Родной LOWER() в SQLite складывает регистр только у
                # латиницы: «алишер» не нашёл бы «Алишер». Питоновский
                # lower() знает про кириллицу.
                await conn.create_function("pylower", 1, _pylower, deterministic=True)
                _conn = conn
    return _conn


@asynccontextmanager
async def _db():
    """Общий коннект в том же виде, в каком раньше был свой на запрос."""
    yield await connect()


# то же самое для соседних модулей
session = _db


async def close():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- ИНИЦИАЛИЗАЦИЯ ----------

async def db_init():
    async with _db() as db:
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
                cert_reminder_sent_at TEXT,
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
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS nudges (
                user_id INTEGER PRIMARY KEY,
                sent_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                user_id INTEGER PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
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
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_user ON events (user_id, created_at)"
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
            ("cert_reminder_sent_at", "TEXT"),
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
        cur = await db.execute("SELECT title FROM exam_dates WHERE id = ?", (date_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указана"


# ---------- ДАТЫ: АДМИНКА ----------

async def get_dates_overview() -> list[tuple]:
    """Все даты: (id, title, seats_limit, is_active, confirmed, pending)."""
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
        try:
            cur = await db.execute(
                "UPDATE exam_dates SET title = ? WHERE id = ?", (title, date_id)
            )
        except sqlite3.IntegrityError:
            return "duplicate"
        await db.commit()
        return "ok" if cur.rowcount > 0 else "missing"


async def set_exam_date(date_id: int, exam_date: str | None) -> bool:
    async with _db() as db:
        cur = await db.execute(
            "UPDATE exam_dates SET exam_date = ? WHERE id = ?", (exam_date, date_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def set_date_limit(date_id: int, seats_limit: int) -> bool:
    async with _db() as db:
        cur = await db.execute(
            "UPDATE exam_dates SET seats_limit = ? WHERE id = ?", (seats_limit, date_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_date(date_id: int) -> str:
    """Удаляет дату. Если по ней уже есть заявки — прячет её из списка ('archived')."""
    async with _db() as db:
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
    async with _db() as db:
        cur = await db.execute(
            "UPDATE exam_dates SET is_active = 1 WHERE id = ?", (date_id,)
        )
        await db.commit()
        return cur.rowcount > 0


# ---------- ПОИСК ----------

async def search_bookings(query: str, limit: int = 20) -> list[tuple]:
    """(id, full_name, applicant_name, username, user_id, status, date_title).

    Ищем по имени владельца аккаунта, по имени записанного, по username и по
    числовому id — админ обычно помнит что-то одно из этого.
    """
    query = (query or "").strip().lstrip("@")
    if not query:
        return []

    like = f"%{query.lower()}%"
    params = [like, like, like]
    numeric = ""
    if query.isdigit():
        # число может быть и Telegram ID, и номером заявки
        numeric = " OR b.user_id = ? OR b.id = ?"
        params += [int(query), int(query)]

    async with _db() as db:
        cur = await db.execute(
            f"""SELECT b.id, b.full_name, b.applicant_name, b.username,
                       b.user_id, b.status, d.title
                FROM bookings b
                LEFT JOIN exam_dates d ON d.id = b.date_id
                WHERE pylower(b.full_name) LIKE ?
                   OR pylower(b.applicant_name) LIKE ?
                   OR pylower(b.username) LIKE ?
                   {numeric}
                ORDER BY b.id DESC
                LIMIT ?""",
            (*params, limit),
        )
        return await cur.fetchall()


# ---------- РАССЫЛКА ПО ДАТЕ ----------

async def get_date_recipients(date_id: int) -> list[int]:
    """Уникальные аккаунты с действующей заявкой на дату.

    Именно аккаунты, а не заявки: с одного аккаунта могли записать друзей,
    и слать один и тот же текст туда трижды незачем.
    """
    async with _db() as db:
        cur = await db.execute(
            """SELECT DISTINCT user_id FROM bookings
               WHERE date_id = ? AND status IN (?, ?)""",
            (date_id, PENDING, CONFIRMED),
        )
        return [row[0] for row in await cur.fetchall()]


# ---------- ИТОГ ЭКЗАМЕНА ----------

async def set_outcome(booking_id: int, outcome: str,
                      admin_id: int, admin_name: str) -> bool:
    """Проставляет итог. Переставить можно — пишем последнего, кто трогал."""
    if outcome not in OUTCOMES:
        return False
    async with _db() as db:
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
    async with _db() as db:
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


# ---------- СЛУЖЕБНЫЕ ОТМЕТКИ ----------

async def get_meta(key: str) -> str | None:
    async with _db() as db:
        cur = await db.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_meta(key: str, value: str):
    async with _db() as db:
        await db.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


# ---------- ВОЗВРАТ БРОШЕННЫХ ЗАПИСЕЙ ----------

async def get_abandoned_users(cutoff: str) -> list[int]:
    """Кто начал запись, но не создал заявку, и молчит дольше cutoff.

    Наличие любой заявки (в том числе отменённой) значит, что запись доведена до
    конца — таким не пишем. Один раз на человека: строка в nudges.
    """
    async with _db() as db:
        cur = await db.execute(
            """SELECT e.user_id
               FROM events e
               LEFT JOIN bookings b ON b.user_id = e.user_id
               LEFT JOIN nudges n ON n.user_id = e.user_id
               WHERE b.id IS NULL AND n.user_id IS NULL
               GROUP BY e.user_id
               HAVING MAX(e.created_at) < ?""",
            (cutoff,),
        )
        return [row[0] for row in await cur.fetchall()]


async def mark_nudged(user_id: int):
    async with _db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO nudges (user_id, sent_at) VALUES (?, ?)",
            (user_id, _now()),
        )
        await db.commit()


async def get_nudge_stats() -> dict:
    """Сколько написали и сколько из них после этого записались."""
    async with _db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM nudges")
        (sent,) = await cur.fetchone()
        cur = await db.execute(
            """SELECT COUNT(*) FROM nudges n
               WHERE EXISTS (SELECT 1 FROM bookings b
                             WHERE b.user_id = n.user_id AND b.created_at > n.sent_at)"""
        )
        (returned,) = await cur.fetchone()
    return {
        "sent": sent,
        "returned": returned,
        "pct": round(returned * 100 / sent) if sent else 0,
    }


# ---------- РЕФЕРАЛЫ ----------

async def get_client_name(user_id: int) -> str | None:
    """Имя из последней заявки — единственное место, где оно у нас есть."""
    async with _db() as db:
        cur = await db.execute(
            "SELECT full_name FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def add_referral(user_id: int, referrer_id: int) -> bool:
    """Пишем только при первом запуске и только чужую ссылку."""
    if user_id == referrer_id:
        return False
    async with _db() as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO referrals (user_id, referrer_id, created_at) "
            "VALUES (?, ?, ?)",
            (user_id, referrer_id, _now()),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_referrer(user_id: int) -> int | None:
    async with _db() as db:
        cur = await db.execute(
            "SELECT referrer_id FROM referrals WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_top_referrers(limit: int = 10) -> list[tuple]:
    """(referrer_id, имя, приведено, из них дошли до оплаты)."""
    async with _db() as db:
        cur = await db.execute(
            """SELECT r.referrer_id,
                      (SELECT b.full_name FROM bookings b
                        WHERE b.user_id = r.referrer_id
                        ORDER BY b.id DESC LIMIT 1),
                      COUNT(*),
                      COUNT(DISTINCT CASE WHEN EXISTS (
                          SELECT 1 FROM bookings b2
                           WHERE b2.user_id = r.user_id AND b2.status = ?
                      ) THEN r.user_id END)
               FROM referrals r
               GROUP BY r.referrer_id
               ORDER BY 4 DESC, 3 DESC
               LIMIT ?""",
            (CONFIRMED, limit),
        )
        return await cur.fetchall()


# ---------- ПРОДЛЕНИЕ СЕРТИФИКАТА ----------

CERT_YEARS = 3
CERT_WARN_MONTHS = 2


async def get_cert_renewals(today_iso: str) -> list[tuple]:
    """(booking_id, user_id, exam_date) — у кого до истечения осталось меньше
    CERT_WARN_MONTHS и срок ещё не вышел.

    Провалившим и не пришедшим не пишем: сертификата у них нет. Заявки без
    проставленного итога включаем — админы часто не успевают их отметить.
    """
    async with _db() as db:
        cur = await db.execute(
            f"""SELECT b.id, b.user_id, d.exam_date
                FROM bookings b
                JOIN exam_dates d ON d.id = b.date_id
                WHERE b.status = ?
                  AND b.cert_reminder_sent_at IS NULL
                  AND (b.outcome IS NULL OR b.outcome = ?)
                  AND d.exam_date IS NOT NULL
                  AND date(d.exam_date, '+{CERT_YEARS} years',
                           '-{CERT_WARN_MONTHS} months') <= ?
                  AND date(d.exam_date, '+{CERT_YEARS} years') > ?""",
            (CONFIRMED, PASSED, today_iso, today_iso),
        )
        return await cur.fetchall()


async def mark_cert_reminded(booking_id: int):
    async with _db() as db:
        await db.execute(
            "UPDATE bookings SET cert_reminder_sent_at = ? WHERE id = ?",
            (_now(), booking_id),
        )
        await db.commit()


# ---------- ВОРОНКА ----------

async def log_event(user_id: int, step: str):
    """Одно событие на шаг. Ошибку логирования глотаем: воронка не должна
    ронять диалог с клиентом."""
    try:
        async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
        await db.execute(
            "UPDATE bookings SET reminder_sent_at = ? WHERE id = ?",
            (_now(), booking_id),
        )
        await db.commit()


# ---------- ЯЗЫК КЛИЕНТА ----------

async def get_user_lang(user_id: int) -> str | None:
    """None — клиент ещё не выбирал язык."""
    async with _db() as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def get_user_langs(user_ids: list[int]) -> dict[int, str]:
    """Языки пачкой: в рассылках получателей сотни, и запрос на каждого
    из них — это сотни обращений к базе в одном цикле."""
    if not user_ids:
        return {}
    async with _db() as db:
        marks = ",".join("?" * len(user_ids))
        cur = await db.execute(
            f"SELECT user_id, lang FROM users WHERE user_id IN ({marks})",
            tuple(user_ids),
        )
        return {row[0]: row[1] for row in await cur.fetchall()}


async def set_user_lang(user_id: int, lang: str):
    async with _db() as db:
        await db.execute(
            """INSERT INTO users (user_id, lang, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   lang = excluded.lang, updated_at = excluded.updated_at""",
            (user_id, lang, _now()),
        )
        await db.commit()


# ---------- ЗАЯВКИ ----------

async def has_active_booking(user_id: int) -> bool:
    async with _db() as db:
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
    async with _tx_lock, _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
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
    async with _db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO admin_messages VALUES (?, ?, ?)",
            (booking_id, admin_id, message_id),
        )
        await db.commit()


async def get_admin_messages(booking_id: int) -> list[tuple[int, int]]:
    async with _db() as db:
        cur = await db.execute(
            "SELECT admin_id, message_id FROM admin_messages WHERE booking_id = ?",
            (booking_id,),
        )
        return await cur.fetchall()


# ---------- СТАТИСТИКА И ЭКСПОРТ ----------

async def get_stats() -> dict:
    async with _db() as db:
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
    async with _db() as db:
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
