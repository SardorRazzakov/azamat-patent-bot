"""Автоответ в личных сообщениях владельца через Telegram Business.

Бот подключён к личному аккаунту владельца и отвечает от его имени: клиент
видит имя и аватар владельца, бота в интерфейсе нет. Апдейты приходят
отдельным типом business_message и обычных хендлеров не касаются — здесь
свой роутер и свой обсервер.

Поведение: один автоответ на диалог, на любое сообщение — текст, голосовое,
фото. Клиенты часто начинают именно с них, и раньше такие люди оставались
без ответа. Если владелец написал в чат сам, бот замолкает там навсегда.

КАК ОТЛИЧИТЬ КЛИЕНТА ОТ ВЛАДЕЛЬЦА. Поля is_outgoing в Bot API нет:
business_message приходит и на входящие, и на исходящие сообщения чата.
Ошибиться здесь дорого — перепутав, бот начнёт отвечать владельцу в его же
переписках. Поэтому два независимых признака:

  * sender_business_bot заполнен только у исходящих, отправленных ботом от
    имени бизнес-аккаунта. Это наши собственные ответы: их пропускаем, иначе
    бот примет свой ответ за вмешательство владельца;
  * владелец — это BusinessConnection.user, его отдаёт
    bot.get_business_connection(). Сравнение from_user.id с chat.id работало
    бы только потому, что в приватном чате они совпадают, и молча сломалось
    бы на любом другом раскладе.

Если владельца выяснить не удалось, бот молчит: промолчать безопаснее, чем
написать не тому.
"""

from aiogram import Bot, Router
from aiogram.types import BusinessConnection, Message

import config
import db

router = Router(name="business")

# Текст один и не идёт через texts.py: язык клиента здесь неизвестен —
# он ещё ничего не выбирал и в users его нет.
REPLY = (
    "Assalomu alaykum! 👋\n\n"
    "👥 Guruhimiz — har kuni bepul imtihon savollari:\n"
    "https://t.me/sertifikat_ru_uz\n\n"
    "Rus tili sertifikati bo'yicha ma'lumot beraman.\n\n"
    "💰 Narxlar:\n"
    "• Faqat imtihon — 1 400 000 so'm\n"
    "• Imtihon + o'quv kursi — 1 600 000 so'm\n\n"
    "📄 Kerakli hujjatlar:\n"
    "• Pasport nusxasi\n"
    "• To'lov cheki\n\n"
    "📍 Manzil: Toshkent, Parkent ko'chasi, 331\n\n"
    "💳 O'zbekistondan to'lov:\n"
    "Payme — https://payme.uz/fallback/merchant/?id=6a4673b9ccf9c1de0aa04520\n"
    "Click — https://indoor.click.uz/pay?id=0105991&t=0\n\n"
    "💳 Rossiyadan to'lov (Sberbank):\n"
    "Karta: 2202 2069 3871 6664\n"
    "Qabul qiluvchi: Юсупов Азамат\n"
    "• Faqat imtihon — 9 500 ₽\n"
    "• Imtihon + kurs — 11 000 ₽\n\n"
    "Qaysi sanaga yozilmoqchisiz?"
)

# Сколько текста клиента попадает в уведомление: длинное сообщение
# в сводке ни к чему, суть видна по первым строкам.
NOTIFY_TEXT_LIMIT = 200

# Чем описать сообщение без текста. Клиенты часто начинают голосовым или
# сразу шлют фото паспорта — в сводке важно, что именно пришло.
MESSAGE_KINDS = (
    ("voice", "голосовое"),
    ("photo", "фото"),
    ("video", "видео"),
    ("document", "файл"),
    ("sticker", "стикер"),
)


def describe(message: Message) -> str:
    """Текст сообщения, а если текста нет — его тип.

    Подпись к медиа Telegram кладёт в caption, а не в text: без неё фото
    паспорта с подписью «Mana pasport» выглядело бы в сводке просто «фото».
    """
    for value in (message.text, message.caption):
        value = (value or "").strip()
        if value:
            return value[:NOTIFY_TEXT_LIMIT]

    for field, name in MESSAGE_KINDS:
        if getattr(message, field, None):
            return name
    return "другое"


# id владельца на подключение. В памяти намеренно: значение всегда можно
# перезапросить, а неверно переживший рестарт владелец был бы опаснее.
_owners: dict[str, int] = {}


async def owner_id(bot: Bot, connection_id: str) -> int | None:
    """id владельца бизнес-аккаунта. None — выяснить не удалось."""
    if connection_id not in _owners:
        try:
            connection = await bot.get_business_connection(connection_id)
        except Exception as e:
            print(f"[business] не удалось получить подключение {connection_id}: {e}")
            return None
        _owners[connection_id] = connection.user.id
    return _owners[connection_id]


@router.business_connection()
async def connection_changed(event: BusinessConnection):
    """Подключение создали, включили или выключили.

    Хендлер нужен и сам по себе — он держит кэш владельца свежим, — и ради
    подписки: allowed_updates собирается из зарегистрированных хендлеров,
    без него апдейт business_connection бот запрашивать не станет.
    """
    _owners[event.id] = event.user.id
    state = "включено" if event.is_enabled else "выключено"
    print(f"[business] подключение {event.id}: {state}, владелец {event.user.id}")


async def notify_new_client(bot: Bot, message: Message):
    """Сводка о новом клиенте тому, кто разбирает личку владельца.

    Обычным сообщением от бота, без business_connection_id: это личка
    получателя, а не переписка от имени владельца.

    Ошибку глотаем: клиент свой ответ уже получил, и ронять из-за
    несостоявшейся сводки хендлер незачем.
    """
    if not config.BUSINESS_NOTIFY_ID:
        return

    user = message.from_user
    username = f"@{user.username}" if user.username else "без username"
    text = describe(message)

    try:
        await bot.send_message(
            config.BUSINESS_NOTIFY_ID,
            f"💬 Новый клиент в личке\n"
            f"Имя: {user.full_name}\n"
            f"{username}\n"
            f"Первое сообщение: {text}\n\n"
            f"Клиенту отправлен прайс и задан вопрос о дате.",
        )
    except Exception as e:
        print(f"[business] уведомление о клиенте {user.id} не ушло: {e}")


@router.business_message()
async def business_message(message: Message, bot: Bot):
    # Наш собственный ответ вернулся тем же апдейтом — не он вмешательство
    # владельца и не повод для второго ответа.
    if message.sender_business_bot is not None:
        return

    connection_id = message.business_connection_id
    if not connection_id or message.from_user is None:
        return

    owner = await owner_id(bot, connection_id)
    if owner is None:
        return

    # Владелец ответил сам — этот чат теперь его, бот сюда больше не пишет.
    if message.from_user.id == owner:
        await db.mark_business_takeover(message.chat.id)
        return

    if not await db.claim_business_reply(message.chat.id):
        return

    try:
        # business_connection_id обязателен: без него ответ уйдёт от имени
        # бота, а не владельца. Message.answer() подставил бы его сам, но
        # здесь это слишком важно, чтобы полагаться на умолчание.
        await bot.send_message(
            chat_id=message.chat.id,
            text=REPLY,
            business_connection_id=connection_id,
        )
    except Exception as e:
        print(f"[business] автоответ в чат {message.chat.id} не ушёл: {e}")
        return

    # Только после того, как ответ действительно ушёл: сводка о клиенте,
    # которому ничего не отправили, вводила бы в заблуждение.
    await notify_new_client(bot, message)
