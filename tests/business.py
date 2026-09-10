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
os.environ["BUSINESS_NOTIFY_ID"] = "555"

from aiogram.types import (  # noqa: E402
    Chat, Document, Message, PhotoSize, Sticker, User, Video, Voice,
)

import config  # noqa: E402
import db  # noqa: E402
from handlers import business  # noqa: E402

OWNER_ID = 500
CLIENT_ID = 900
OUR_BOT_ID = 42
NOTIFY_ID = 555


class FakeBot:
    """Отдаёт владельца подключения и копит отправленные сообщения."""

    def __init__(self, owner: int | None = OWNER_ID, notify_fails: bool = False,
                 voice_fails: bool = False):
        self.owner = owner
        self.notify_fails = notify_fails
        self.voice_fails = voice_fails
        self.sent: list[dict] = []           # ответы клиенту
        self.notified: list[dict] = []       # сводки о новом клиенте
        self.voices: list[dict] = []         # голосовые приветствия
        self.order: list[str] = []           # что за чем ушло

    async def get_business_connection(self, connection_id: str):
        if self.owner is None:
            raise RuntimeError("подключение недоступно")

        class Connection:
            user = User(id=self.owner, is_bot=False, first_name="Владелец")

        return Connection()

    async def send_message(self, chat_id, text, business_connection_id=None, **kw):
        entry = {
            "chat_id": chat_id,
            "text": text,
            "business_connection_id": business_connection_id,
        }
        # Сводка идёт без business_connection_id — по нему их и различаем.
        if business_connection_id is None:
            if self.notify_fails:
                raise RuntimeError("получатель заблокировал бота")
            self.notified.append(entry)
            self.order.append("notify")
        else:
            self.sent.append(entry)
            self.order.append("reply")

    async def send_voice(self, chat_id, voice, business_connection_id=None, **kw):
        if self.voice_fails:
            raise RuntimeError("файл слишком большой")
        self.voices.append({
            "chat_id": chat_id,
            "business_connection_id": business_connection_id,
        })
        self.order.append("voice")


# Сообщения без текста: у таких клиент присылает голосовое или фото
# паспорта вместо приветствия.
MEDIA = {
    "voice": lambda: {"voice": Voice(file_id="f", file_unique_id="u", duration=3)},
    "photo": lambda: {"photo": [PhotoSize(file_id="f", file_unique_id="u",
                                          width=90, height=90)]},
    "video": lambda: {"video": Video(file_id="f", file_unique_id="u",
                                     width=90, height=90, duration=5)},
    "document": lambda: {"document": Document(file_id="f", file_unique_id="u")},
    "sticker": lambda: {"sticker": Sticker(file_id="f", file_unique_id="u",
                                           type="regular", width=90, height=90,
                                           is_animated=False, is_video=False)},
}


def incoming(chat_id: int, *, sender: int, text: str | None = "salom",
             from_our_bot: bool = False, username: str | None = None,
             kind: str | None = None, caption: str | None = None) -> Message:
    sender_bot = None
    if from_our_bot:
        sender_bot = User(id=OUR_BOT_ID, is_bot=True, first_name="Бот")
    # У медиасообщения text пустой — подпись Telegram кладёт в caption
    media = MEDIA[kind]() if kind else {}
    return Message(
        message_id=1,
        date=0,
        chat=Chat(id=chat_id, type="private"),
        from_user=User(id=sender, is_bot=False, first_name="Кто-то",
                       username=username),
        text=None if kind else text,
        caption=caption,
        business_connection_id="conn-1",
        sender_business_bot=sender_bot,
        **media,
    )


def fresh_bot(owner: int | None = OWNER_ID, notify_fails: bool = False,
              voice_fails: bool = False) -> FakeBot:
    # кэш владельца живёт в модуле и между случаями его надо сбрасывать
    business._owners.clear()
    return FakeBot(owner, notify_fails, voice_fails)


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


async def replies_to_messages_without_text():
    """Голосовое и фото тоже получают ответ.

    Клиенты часто начинают голосовым или сразу шлют фото паспорта. Пока
    ответ требовал текста, такие люди оставались без него вовсе.
    """
    for kind, chat in (("voice", 1004), ("photo", 1012)):
        bot = fresh_bot()

        await business.business_message(
            incoming(chat, sender=CLIENT_ID, kind=kind), bot
        )
        assert len(bot.sent) == 1, f"{kind}: ответов {len(bot.sent)}"
        assert bot.sent[0]["text"] == business.REPLY

        # правило «один ответ на диалог» на медиа распространяется тоже
        await business.business_message(
            incoming(chat, sender=CLIENT_ID, kind=kind), bot
        )
        assert len(bot.sent) == 1, f"{kind}: ответил повторно"


async def sends_voice_before_price():
    """Голос идёт первым, следом прайс — в таком порядке их и слушают."""
    assert business.VOICE_PATH.exists(), (
        f"нет файла приветствия: {business.VOICE_PATH}"
    )
    bot, chat = fresh_bot(), 1040

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)

    assert len(bot.voices) == 1, f"голосовых отправлено {len(bot.voices)}"
    assert bot.voices[0]["chat_id"] == chat
    # без него голосовое уйдёт от имени бота, а не владельца
    assert bot.voices[0]["business_connection_id"] == "conn-1"
    assert bot.order[:2] == ["voice", "reply"], f"порядок отправки: {bot.order}"

    # правило «один ответ на диалог» распространяется и на голос
    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.voices) == 1, "голосовое ушло повторно"


async def voice_failure_does_not_block_price():
    """Голосовое не ушло — прайс всё равно должен дойти.

    Иначе сбойный файл оставлял бы клиента вообще без ответа, а чат при
    этом уже помечен отвеченным: второй попытки не будет.
    """
    bot, chat = fresh_bot(voice_fails=True), 1041

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)

    assert not bot.voices, "голосовое записалось, хотя отправка упала"
    assert len(bot.sent) == 1, "из-за голосового не ушёл прайс"
    assert bot.sent[0]["text"] == business.REPLY


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


async def notifies_about_new_client():
    """Сводка уходит вместе с первым ответом — и только с ним."""
    bot, chat = fresh_bot(), 1008

    await business.business_message(
        incoming(chat, sender=CLIENT_ID, text="Salom, narxi qancha?",
                 username="client"),
        bot,
    )
    assert len(bot.notified) == 1, f"сводок отправлено {len(bot.notified)}"

    note = bot.notified[0]
    assert note["chat_id"] == NOTIFY_ID, f"сводка ушла на {note['chat_id']}"
    # это личка получателя, а не переписка от имени владельца
    assert note["business_connection_id"] is None, (
        "сводка ушла с business_connection_id — то есть от имени владельца"
    )
    for part in ("Новый клиент", "@client", "Salom, narxi qancha?"):
        assert part in note["text"], f"в сводке нет «{part}»"


async def notification_shows_message_kind():
    """Без текста в сводке стоит тип сообщения, а не пустое место.

    Иначе получатель видит «Первое сообщение:» и обрыв — непонятно, то ли
    клиент прислал пустое, то ли сводка сломалась.
    """
    kinds = {
        "voice": "голосовое",
        "photo": "фото",
        "video": "видео",
        "document": "файл",
        "sticker": "стикер",
    }
    for i, (kind, expected) in enumerate(kinds.items()):
        bot, chat = fresh_bot(), 1020 + i

        await business.business_message(
            incoming(chat, sender=CLIENT_ID, kind=kind), bot
        )
        assert len(bot.notified) == 1, f"{kind}: сводок {len(bot.notified)}"

        line = f"Первое сообщение: {expected}"
        assert line in bot.notified[0]["text"], (
            f"{kind}: в сводке нет «{line}»\n{bot.notified[0]['text']}"
        )

    # Неизвестный тип и текст из одних пробелов сводятся к «другое».
    bot, chat = fresh_bot(), 1030
    await business.business_message(
        incoming(chat, sender=CLIENT_ID, text="   "), bot
    )
    assert len(bot.sent) == 1, "пробелы остались без ответа"
    assert "Первое сообщение: другое" in bot.notified[0]["text"]


async def notification_prefers_caption_over_kind():
    """Подпись к фото важнее самого факта, что это фото.

    Telegram кладёт её в caption, а не в text. Без этого клиент, приславший
    паспорт с подписью, выглядел бы в сводке просто как «фото» — а там как
    раз и сказано, что именно он прислал.
    """
    bot, chat = fresh_bot(), 1031

    await business.business_message(
        incoming(chat, sender=CLIENT_ID, kind="photo",
                 caption="Mana pasport nusxasi"),
        bot,
    )
    assert len(bot.sent) == 1, "фото с подписью осталось без ответа"

    note = bot.notified[0]["text"]
    assert "Первое сообщение: Mana pasport nusxasi" in note, note
    assert "фото" not in note, f"тип перебил подпись:\n{note}"

    # Подпись из одних пробелов подписью не считается — остаётся тип.
    bot, chat = fresh_bot(), 1032
    await business.business_message(
        incoming(chat, sender=CLIENT_ID, kind="photo", caption="   "), bot
    )
    assert "Первое сообщение: фото" in bot.notified[0]["text"]


async def no_notification_without_reply():
    """Повторное сообщение ответа не даёт — значит и сводки быть не должно."""
    bot, chat = fresh_bot(), 1009

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.notified) == 1

    for _ in range(3):
        await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.notified) == 1, f"сводок стало {len(bot.notified)}"

    # владелец забрал чат — тоже без ответа и без сводки
    await business.business_message(incoming(chat, sender=OWNER_ID), bot)
    assert len(bot.notified) == 1, "вмешательство владельца дало сводку"


async def works_without_notify_id():
    """Переменная не задана — клиент получает ответ как раньше."""
    saved = config.BUSINESS_NOTIFY_ID
    config.BUSINESS_NOTIFY_ID = None
    try:
        bot, chat = fresh_bot(), 1010
        await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
        assert len(bot.sent) == 1, "без BUSINESS_NOTIFY_ID сломался сам ответ"
        assert not bot.notified, "сводка ушла, хотя получатель не задан"
    finally:
        config.BUSINESS_NOTIFY_ID = saved


async def notify_failure_does_not_break_reply():
    """Сводка не дошла — клиент своё уже получил, падать незачем."""
    bot, chat = fresh_bot(notify_fails=True), 1011

    await business.business_message(incoming(chat, sender=CLIENT_ID), bot)
    assert len(bot.sent) == 1, "ответ клиенту не ушёл из-за сводки"
    assert not bot.notified

    # чат помечен отвеченным: второй раз клиента не побеспокоят
    replied_at, _ = await db.get_business_chat(chat)
    assert replied_at is not None


CHECKS = (
    replies_once_per_chat,
    silent_after_owner_took_over,
    owner_takeover_after_reply,
    replies_to_messages_without_text,
    sends_voice_before_price,
    voice_failure_does_not_block_price,
    ignores_own_reply_echo,
    silent_when_owner_unknown,
    claim_is_atomic,
    notifies_about_new_client,
    notification_shows_message_kind,
    notification_prefers_caption_over_kind,
    no_notification_without_reply,
    works_without_notify_id,
    notify_failure_does_not_break_reply,
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
