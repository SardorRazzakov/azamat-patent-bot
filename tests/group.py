"""Ответы бота в группе. Запуск: python tests/group.py

Группа на две с лишним тысячи участников: цена ошибки здесь — не молчание,
а рассылка. Поэтому главное, что проверяется, — ограничение «один ответ
человеку в сутки» и его атомарность: два сообщения подряд приходят разными
апдейтами и обрабатываются параллельно, а ответ должен уйти ровно один.

Хендлер вызывается по-настоящему поверх временной базы; вместо Bot
подставлена заглушка, которая копит отправленное вместо отправки.
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

_TMP = tempfile.mkdtemp(prefix="patentbot-group-")
os.environ["DB_PATH"] = os.path.join(_TMP, "g.db")
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")

from aiogram.types import Chat, Message, User  # noqa: E402

import db  # noqa: E402
from handlers import group  # noqa: E402

CHAT_ID = -1001234567890
BOT_ID = 42
GROUP_ADMIN = 500
PERSON = 900
OTHER = 901


class FakeBot:
    """Отдаёт админов группы и копит ответы вместо отправки."""

    id = BOT_ID

    def __init__(self, admins: set[int] | None = {GROUP_ADMIN}):
        self.admins = admins
        self.sent: list[Message] = []

    async def get_chat_administrators(self, chat_id: int):
        if self.admins is None:
            raise RuntimeError("Telegram недоступен")

        class Member:
            def __init__(self, uid):
                self.user = User(id=uid, is_bot=False, first_name="Админ")

        return [Member(uid) for uid in self.admins]


class Msg(Message):
    """Message с перехваченным reply(): настоящий ушёл бы в сеть."""

    model_config = {"extra": "allow"}

    async def reply(self, text, reply_markup=None, **kw):
        self._sink.append({"text": text, "markup": reply_markup,
                           "reply_to": self.message_id})


def message(text: str | None, *, sender: int = PERSON, chat_type: str = "supergroup",
            reply_to: Message | None = None, is_bot: bool = False,
            sender_chat: Chat | None = None, sink: list | None = None) -> Msg:
    m = Msg(
        message_id=7,
        date=0,
        chat=Chat(id=CHAT_ID, type=chat_type),
        from_user=User(id=sender, is_bot=is_bot, first_name="Кто-то"),
        text=text,
        reply_to_message=reply_to,
        sender_chat=sender_chat,
    )
    m._sink = sink if sink is not None else []
    return m


def from_bot() -> Message:
    return Message(
        message_id=1, date=0,
        chat=Chat(id=CHAT_ID, type="supergroup"),
        from_user=User(id=BOT_ID, is_bot=True, first_name="Бот"),
        text="Assalomu alaykum!",
    )


def from_person() -> Message:
    return Message(
        message_id=2, date=0,
        chat=Chat(id=CHAT_ID, type="supergroup"),
        from_user=User(id=OTHER, is_bot=False, first_name="Другой"),
        text="salom",
    )


def fresh(admins: set[int] | None = {GROUP_ADMIN}) -> FakeBot:
    group._admins.clear()          # кэш админов живёт в модуле
    return FakeBot(admins)


async def wipe():
    async with db.writer() as conn:
        await conn.execute("DELETE FROM group_replies")
        await conn.commit()


# ---------- ПРОВЕРКИ ----------

async def replies_once_per_day():
    """Первое сообщение — ответ, дальше в те же сутки молчание."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(message("salom", sink=sink), bot)
    assert len(sink) == 1, f"на первое сообщение ответов {len(sink)}"
    assert sink[0]["text"] == group.REPLY
    assert sink[0]["reply_to"] == 7, "ответ не реплаем на сообщение человека"
    assert sink[0]["markup"] is not None, "нет кнопки перехода в бот"

    for _ in range(5):
        await group.group_message(message("yana savol", sink=sink), bot)
    assert len(sink) == 1, f"ответил повторно: всего {len(sink)}"


async def replies_again_after_a_day():
    """Через сутки человек снова получает ответ."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(message("salom", sink=sink), bot)
    assert len(sink) == 1

    # отматываем отметку на двое суток назад
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    async with db.writer() as conn:
        await conn.execute(
            "UPDATE group_replies SET replied_at = ? WHERE chat_id = ? AND user_id = ?",
            (stale, CHAT_ID, PERSON),
        )
        await conn.commit()

    await group.group_message(message("salom", sink=sink), bot)
    assert len(sink) == 2, "через сутки ответа не последовало"


async def counter_is_atomic():
    """Сообщения приходят разными апдейтами и могут лечь параллельно.

    Ограничение «раз в сутки» держится только если решение и отметка
    неразделимы. Разнесённая версия отвечает столько раз, сколько пришло
    сообщений, — в группе на 2373 человека это рассылка.
    """
    await wipe()
    bot, sink = fresh(), []

    await asyncio.gather(*(
        group.group_message(message("salom", sink=sink), bot) for _ in range(12)
    ))
    assert len(sink) == 1, f"на 12 одновременных сообщений ответов {len(sink)}"

    # и разным людям одновременно — каждому по одному
    await wipe()
    sink.clear()
    await asyncio.gather(*(
        group.group_message(message("salom", sender=1000 + i, sink=sink), bot)
        for i in range(6) for _ in range(3)
    ))
    assert len(sink) == 6, f"шестерым людям ответов {len(sink)}, ожидалось 6"


async def silent_for_group_admins():
    """Админам группы приглашение в бот не нужно."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(message("salom", sender=GROUP_ADMIN, sink=sink), bot)
    assert not sink, "ответил админу группы"
    assert await db.get_group_reply(CHAT_ID, GROUP_ADMIN) is None, "админ занял слот"


async def silent_on_reply_to_person():
    """Реплай другому человеку — разговор между участниками."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(
        message("ha, to'g'ri", reply_to=from_person(), sink=sink), bot
    )
    assert not sink, "встрял в разговор двух людей"


async def answers_reply_to_bot():
    """Реплай самому боту — это вопрос боту, на него отвечаем."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(
        message("qanday yozilaman?", reply_to=from_bot(), sink=sink), bot
    )
    assert len(sink) == 1, "не ответил на реплай самому себе"


async def ignores_messages_without_text():
    """Стикеры, фото, вступления в группу приходят без text."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(message(None, sink=sink), bot)
    await group.group_message(message("   ", sink=sink), bot)
    assert not sink, "ответил на сообщение без текста"
    assert await db.get_group_reply(CHAT_ID, PERSON) is None, "слот потрачен зря"


async def ignores_bots_and_anonymous():
    """Другие боты и посты от имени канала или анонимного админа."""
    await wipe()
    bot, sink = fresh(), []

    await group.group_message(message("реклама", is_bot=True, sink=sink), bot)
    await group.group_message(
        message("от канала", sender_chat=Chat(id=CHAT_ID, type="channel"), sink=sink),
        bot,
    )
    assert not sink, "ответил боту или анонимному отправителю"


async def silent_when_admins_unknown():
    """Не выяснив админов, молчим: ответить админу хуже, чем промолчать."""
    await wipe()
    bot, sink = fresh(admins=None), []

    await group.group_message(message("salom", sink=sink), bot)
    assert not sink, "ответил, не зная списка админов"
    assert await db.get_group_reply(CHAT_ID, PERSON) is None, "слот потрачен зря"


CHECKS = (
    replies_once_per_day,
    replies_again_after_a_day,
    counter_is_atomic,
    silent_for_group_admins,
    silent_on_reply_to_person,
    answers_reply_to_bot,
    ignores_messages_without_text,
    ignores_bots_and_anonymous,
    silent_when_admins_unknown,
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
