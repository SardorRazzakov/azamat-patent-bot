"""Ответ на сообщения в группе: приглашение перейти в бот.

Бот состоит в группе @sertifikat_ru_uz. До этого модуля групповые сообщения
доезжали до клиентского `@router.message()` без фильтров и получали в ответ
«Тушунмадим» с кнопками — поведение из личного диалога, в группе неуместное.

Роутер подключается ПЕРВЫМ и отфильтрован по типу чата. Первым — потому что
выше в цепочке стоит админский роутер, чьи FSM-шаги принимают любой текст без
слэша: пока админ вводит, скажем, название даты, его сообщение в группе
попало бы в этот шаг. Группа изолируется полностью только так. Побочный
эффект осознанный: /start и /admin, набранные в группе, больше не открывают
там выбор языка и админ-панель.

Фильтр по типу чата обязателен: без него роутер перехватил бы личные диалоги
целиком.

Один ответ человеку в сутки — не украшение. В группе на две с лишним тысячи
участников бот без этого ограничения становится спамом, поэтому счётчик
лежит в базе и переживает редеплой.
"""

from datetime import datetime, timedelta, timezone
from time import monotonic

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import db

router = Router(name="group")
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))

BOT_LINK = "https://t.me/azamat_patent_bot"

# Текст один и не идёт через texts.py: аудитория группы почти целиком
# говорит по-узбекски, а язык конкретного человека здесь неизвестен — в
# группу он приходит, ничего не выбирав.
REPLY = (
    "Assalomu alaykum! 👋\n\n"
    "Imtihonga yozilish, sanalar, narx va barcha ma'lumotlar botimizda.\n\n"
    "Quyidagi tugmani bosing yoki @azamat_patent_bot ga yozing."
)

BUTTON = "📝 Botni ochish"

# Через сколько человеку можно ответить снова
REPLY_COOLDOWN_HOURS = 24

# Список админов группы меняется редко, а сообщений много: без кэша это
# запрос к Telegram на каждое из них.
ADMINS_TTL_SECONDS = 600
_admins: dict[int, tuple[float, set[int]]] = {}


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTON, url=BOT_LINK)]
    ])


async def admin_ids(bot: Bot, chat_id: int) -> set[int] | None:
    """id админов группы. None — выяснить не удалось."""
    cached = _admins.get(chat_id)
    if cached and monotonic() - cached[0] < ADMINS_TTL_SECONDS:
        return cached[1]

    try:
        members = await bot.get_chat_administrators(chat_id)
    except Exception as e:
        print(f"[group] не удалось получить админов чата {chat_id}: {e}")
        return None

    ids = {m.user.id for m in members if m.user}
    _admins[chat_id] = (monotonic(), ids)
    return ids


@router.message()
async def group_message(message: Message, bot: Bot):
    # Анонимный админ и посты от имени канала приходят без человека в
    # from_user — отвечать там некому.
    if message.sender_chat is not None or message.from_user is None:
        return

    # Другие боты в группе разговор не ведут.
    if message.from_user.is_bot:
        return

    # Стикеры, фото, голосовые, вступления в группу — всё без текста.
    if not (message.text or "").strip():
        return

    # Реплай другому человеку — это разговор между участниками, встревать
    # незачем. Реплай самому боту при этом остаётся вопросом боту.
    replied = message.reply_to_message
    if replied is not None:
        answered_bot = replied.from_user is not None and replied.from_user.id == bot.id
        if not answered_bot:
            return

    # Админам группы приглашение в бот не нужно. Не сумев выяснить список,
    # молчим: ответить админу хуже, чем промолчать разок.
    admins = await admin_ids(bot, message.chat.id)
    if admins is None or message.from_user.id in admins:
        return

    cutoff = (datetime.now(timezone.utc)
              - timedelta(hours=REPLY_COOLDOWN_HOURS)).isoformat()
    if not await db.claim_group_reply(message.chat.id, message.from_user.id, cutoff):
        return

    try:
        # Реплаем, чтобы в общем потоке было видно, кому адресовано.
        await message.reply(REPLY, reply_markup=keyboard())
    except Exception as e:
        print(f"[group] ответ в чат {message.chat.id} не ушёл: {e}")
