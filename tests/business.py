"""Автоответ в личных чатах владельца. Запуск: python tests/business.py

Здесь проверяется решение «отвечать или молчать» — самое опасное место
модуля. business_message приходит и на входящие, и на исходящие сообщения
чата, поля is_outgoing в Bot API нет, и ошибка в различении означает, что
бот начнёт писать владельцу в его собственных переписках.

Хендлер вызывается по-настоящему, поверх временной базы; наружу вместо Bot
подставлена заглушка, которая записывает вызовы вместо отправки.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="patentbot-business-")
os.environ["DB_PATH"] = os.path.join(_TMP, "b.db")
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")

from aiogram.types import Chat, Message, User  # noqa: E402

import db  # noqa: E402
from handlers import business  # noqa: E402

OWNER_ID = 500
CLIENT_ID = 900
OUR_BOT_ID = 42


class FakeBot:
    """Отдаёт владельца подключения и копит отправленные сообщения."""

    def __init__(self, owner: int | None = OWNER_ID):
        self.owner = owner
        self.sent: list[dict] = []

    async def get_business_connection(self, connection_id: str):
        if self.owner is None:
            raise RuntimeError("подключение недоступно")

        class Connection:
            user = User(id=self.owner, is_bot=False, first_name="Владелец")

        return Connection()

    async def send_message(self, chat_id, text, business_connection_id=None, **kw):
        self.sent.append({
            "chat_id": chat_id,
            "text": text,
            "business_connection_id": business_connection_id,
        })


def incoming(chat_id: int, *, sender: int, text: str | None = "salom",
             from_our_bot: bool = False) -> Message:
    sender_bot = None
    if from_our_bot:
        sender_bot = User(id=OUR_BOT_ID, is_bot=True, first_name="Бот")
    return Message(
        message_id=1,
        date=0,
        chat=Chat(id=chat_id, type="private"),
        from_user=User(id=sender, is_bot=False, first_name="Кто-то"),
        text=text,
        business_connection_id="conn-1",
        sender_business_bot=sender_bot,
    )


def fresh_bot(owner: int | None = OWNER_ID) -> FakeBot:
    # кэш владельца живёт в модуле и между случаями его надо сбрасывать
    business._owners.clear()
    return FakeBot(owner)


# ---------- ПРОВЕРКИ ----------

async def replies_once_per_chat():
    """Первое сообщение клиента — ответ, все следующие — молчание."""
    bot, chat = fresh_bot(), 1001

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.sent) == 1, f"на первое сообщение отправлено {len(bot.sent)}"

    sent = bot.sent[0]
    assert sent["chat_id"] == chat
    assert sent["text"] == business.REPLY
    # без него ответ уйдёт от имени бота, а не владельца
    assert sent["business_connection_id"] == "conn-1", (
        f"business_connection_id = {sent['business_connection_id']!r}"
    )

    for _ in range(3):
        await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.sent) == 1, f"на повторные ответил ещё раз: {len(bot.sent)}"


async def silent_after_owner_took_over():
    """Владелец написал сам — бот в этом чате молчит навсегда."""
    bot, chat = fresh_bot(), 1002

    await business.business_message(incoming(chat, sender=OWNER_ID), bot)
    assert not bot.sent, "ответил на сообщение владельца"

    row = await db.get_business_chat(chat)
    assert row is not None and row[1] is True, f"вмешательство не записано: {row}"

    # клиент пишет уже после владельца — автоответа быть не должно
    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert not bot.sent, "ответил в чате, который забрал владелец"


async def owner_takeover_after_reply():
    """Владелец подключился к диалогу позже — факт всё равно записывается."""
    bot, chat = fresh_bot(), 1003

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.sent) == 1

    await business.business_message(incoming(chat, sender=OWNER_ID), bot)
    replied_at, took_over = await db.get_business_chat(chat)
    assert took_over is True, "вмешательство владельца не записано"
    assert replied_at is not None, "отметка об автоответе затёрлась"
    assert len(bot.sent) == 1, "владелец спровоцировал второй ответ"


async def ignores_messages_without_text():
    """Стикеры, фото, голосовые и файлы приходят без text — на них молчим.

    Своей единственной попытки ответа чат при этом не теряет: поздороваться
    в ответ на стикер нечем, но следующее текстовое сообщение ответ получит.
    """
    bot, chat = fresh_bot(), 1004

    await business.business_message(incoming(chat, sender=CLIENT_ID, text=None), bot)
    assert not bot.sent, "ответил на сообщение без текста"
    assert await db.get_business_chat(chat) is None, "чат зря помечен"

    await business.business_message(incoming(chat, sender=CLIENT_ID, text="   "), bot)
    assert not bot.sent, "ответил на пробелы"

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.sent) == 1, "текст после стикера остался без ответа"


async def ignores_own_reply_echo():
    """Собственный ответ бота возвращается тем же апдейтом.

    У него заполнен sender_business_bot. Принять его за вмешательство
    владельца нельзя: это исказило бы учёт живых чатов.
    """
    bot, chat = fresh_bot(), 1005

    await business.business_message(
        incoming(chat, sender=OWNER_ID, from_our_bot=True), bot
    )
    assert not bot.sent, "ответил на собственное эхо"
    assert await db.get_business_chat(chat) is None, (
        "собственный ответ записан как вмешательство владельца"
    )


async def silent_when_owner_unknown():
    """Подключение не отдалось — молчим.

    Промолчать безопаснее, чем написать: не зная владельца, отличить его
    от клиента невозможно.
    """
    bot, chat = fresh_bot(owner=None), 1006

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert not bot.sent, "ответил, не выяснив владельца"
    assert await db.get_business_chat(chat) is None, "чат помечен зря"


async def claim_is_atomic():
    """Два сообщения подряд приходят разными апдейтами и могут лечь парой.

    Ответ должен уйти ровно один: решение и отметка идут одной вставкой.
    """
    bot, chat = fresh_bot(), 1007

    await asyncio.gather(*(
        business.business_message(incoming(chat, sender=CLIENT_ID), bot)
        for _ in range(8)
    ))
    assert len(bot.sent) == 1, f"на 8 одновременных сообщений ответов {len(bot.sent)}"


CHECKS = (
    replies_once_per_chat,
    silent_after_owner_took_over,
    owner_takeover_after_reply,
    ignores_messages_without_text,
    ignores_own_reply_echo,
    silent_when_owner_unknown,
    claim_is_atomic,
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
