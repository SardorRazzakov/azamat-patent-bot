"""Приглашение в группу после подтверждения оплаты.

Запуск: python tests/group_invites.py

Задача целиком про то, кому НЕ отправить: подписанным, уже получившим,
подтверждённым меньше суток назад, клиентам из старой базы. Ошибка тут не
видна в логах — человек просто получает лишнее сообщение, а второй раз
такое уже не отменить.

Настоящие функции db поверх временного файла, вместо Bot — заглушка.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="patentbot-invites-")
os.environ["DB_PATH"] = os.path.join(_TMP, "i.db")
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")

from aiogram.enums import ChatMemberStatus  # noqa: E402

import db  # noqa: E402
import reminders  # noqa: E402


class Member:
    def __init__(self, status, is_member=None):
        self.status = status
        if is_member is not None:
            self.is_member = is_member


class FakeBot:
    """Отдаёт членство по таблице и копит отправленное."""

    def __init__(self, membership: dict[int, object]):
        self.membership = membership
        self.sent: list[tuple[int, str]] = []

    async def get_chat_member(self, chat_id, user_id):
        state = self.membership.get(user_id, "error")
        if state == "error":
            raise RuntimeError("бот не администратор группы")
        return state

    async def send_message(self, user_id, text, reply_markup=None, **kw):
        self.sent.append((user_id, text))


async def reset():
    async with db.writer() as conn:
        for table in ("bookings", "group_invites", "exam_dates", "users"):
            await conn.execute(f"DELETE FROM {table}")
        await conn.commit()


async def booking(user_id: int, *, confirmed_hours_ago: float | None):
    """Подтверждённая заявка. None — подтверждена до появления колонки."""
    async with db.writer() as conn:
        cur = await conn.execute(
            "INSERT INTO exam_dates (title, seats_limit, sort_order) VALUES (?, 0, 0)",
            (f"дата-{user_id}",),
        )
        date_id = cur.lastrowid
        confirmed_at = None
        if confirmed_hours_ago is not None:
            confirmed_at = (datetime.now(timezone.utc)
                            - timedelta(hours=confirmed_hours_ago)).isoformat()
        await conn.execute(
            """INSERT INTO bookings
               (user_id, full_name, username, date_id, passport_file_id,
                receipt_file_id, status, created_at, confirmed_at)
               VALUES (?, '', '', ?, '', '', 'confirmed', ?, ?)""",
            (user_id, date_id, datetime.now(timezone.utc).isoformat(), confirmed_at),
        )
        await conn.commit()


MEMBER = Member(ChatMemberStatus.MEMBER)
LEFT = Member(ChatMemberStatus.LEFT)
KICKED = Member(ChatMemberStatus.KICKED)
ADMIN = Member(ChatMemberStatus.ADMINISTRATOR)
BANNED_BUT_IN = Member(ChatMemberStatus.RESTRICTED, is_member=True)
RESTRICTED_OUT = Member(ChatMemberStatus.RESTRICTED, is_member=False)


# ---------- ПРОВЕРКИ ----------

async def invites_unsubscribed_after_a_day():
    """Не подписан и подтверждён больше суток назад — зовём."""
    await reset()
    await booking(100, confirmed_hours_ago=30)
    bot = FakeBot({100: LEFT})

    assert await reminders.send_group_invites(bot) == 1
    assert [u for u, _ in bot.sent] == [100]
    assert await db.was_group_invited(100), "отметка не поставлена"


async def never_repeats():
    """Второй раз не пишем никогда."""
    await reset()
    await booking(101, confirmed_hours_ago=30)
    bot = FakeBot({101: LEFT})

    await reminders.send_group_invites(bot)
    for _ in range(3):
        await reminders.send_group_invites(bot)
    assert len(bot.sent) == 1, f"отправлено {len(bot.sent)} раз"


async def waits_a_day_after_confirmation():
    """Подтверждён только что — не трогаем, человек занят записью."""
    await reset()
    await booking(102, confirmed_hours_ago=2)
    bot = FakeBot({102: LEFT})

    assert await reminders.send_group_invites(bot) == 0
    assert not bot.sent
    assert not await db.was_group_invited(102), "слот потрачен зря"


async def silent_for_subscribers():
    """Подписанным не пишем, но помечаем — чтобы не проверять их снова."""
    await reset()
    for uid, state in ((103, MEMBER), (104, ADMIN), (105, BANNED_BUT_IN)):
        await booking(uid, confirmed_hours_ago=30)
    bot = FakeBot({103: MEMBER, 104: ADMIN, 105: BANNED_BUT_IN})

    assert await reminders.send_group_invites(bot) == 0
    assert not bot.sent, "написали тому, кто уже в группе"
    for uid in (103, 104, 105):
        assert await db.was_group_invited(uid), f"{uid} не помечен, проверим снова"


async def invites_those_who_left_or_kicked():
    """left, kicked и ограниченный без членства — в группе не состоят."""
    await reset()
    for uid in (106, 107, 108):
        await booking(uid, confirmed_hours_ago=30)
    bot = FakeBot({106: LEFT, 107: KICKED, 108: RESTRICTED_OUT})

    assert await reminders.send_group_invites(bot) == 3
    assert sorted(u for u, _ in bot.sent) == [106, 107, 108]


async def silent_when_membership_unknown():
    """Бот не админ или чат недоступен — молчим и отметку не ставим.

    Отметка означала бы «этому уже написали», и человек не получил бы
    приглашения никогда, хотя причина была во внешних правах.
    """
    await reset()
    await booking(109, confirmed_hours_ago=30)
    bot = FakeBot({})           # get_chat_member всегда падает

    assert await reminders.send_group_invites(bot) == 0
    assert not bot.sent
    assert not await db.was_group_invited(109), (
        "человек помечен из-за чужой ошибки и приглашения уже не получит"
    )

    # права починили — приглашение уходит в следующий круг
    bot.membership[109] = LEFT
    assert await reminders.send_group_invites(bot) == 1


async def skips_old_base():
    """Заявки без confirmed_at — из старой базы, их не трогаем."""
    await reset()
    await booking(110, confirmed_hours_ago=None)
    bot = FakeBot({110: LEFT})

    assert await reminders.send_group_invites(bot) == 0
    assert not bot.sent, "написали клиенту из старой базы"


async def migration_marks_old_clients():
    """Миграция помечает прежних клиентов как уже уведомлённых.

    Проверяется тот самый запрос из db_init на базе, где колонки ещё нет.
    """
    await reset()
    await booking(111, confirmed_hours_ago=None)
    await booking(112, confirmed_hours_ago=None)

    async with db.writer() as conn:
        cur = await conn.execute(
            """INSERT OR IGNORE INTO group_invites (user_id, sent_at)
               SELECT DISTINCT user_id, ? FROM bookings WHERE status = ?""",
            (datetime.now(timezone.utc).isoformat(), db.CONFIRMED),
        )
        await conn.commit()
        assert cur.rowcount == 2, f"помечено {cur.rowcount} вместо 2"

    for uid in (111, 112):
        assert await db.was_group_invited(uid)


CHECKS = (
    invites_unsubscribed_after_a_day,
    never_repeats,
    waits_a_day_after_confirmation,
    silent_for_subscribers,
    invites_those_who_left_or_kicked,
    silent_when_membership_unknown,
    skips_old_base,
    migration_marks_old_clients,
)


async def main() -> int:
    await db.db_init()

    failed = 0
    for check in CHECKS:
        try:
            await check()
        except Exception:
            failed += 1
            print(f"FAIL  {check.__name__}")
            traceback.print_exc()
        else:
            print(f"ok    {check.__name__}")

    await db.close()

    print()
    if failed:
        print(f"провалено проверок: {failed} из {len(CHECKS)}")
    else:
        print(f"все проверки прошли ({len(CHECKS)})")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    sys.exit(code)
