import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

TOKEN = os.environ.get("BOT_TOKEN")


def parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


ADMIN_IDS = parse_admin_ids(
    os.environ.get("ADMIN_IDS") or os.environ.get("ADMIN_ID", "")
)

if not TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN")
if not ADMIN_IDS:
    raise RuntimeError("Не задан ADMIN_IDS (пример: 123456789,987654321)")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

EXAM_DATES = ["15 sentabr", "22 sentabr", "29 sentabr"]
PAYME_LINK = "https://payme.uz/fallback/merchant/?id=6a4673b9ccf9c1de0aa04520"
CLICK_LINK = "https://indoor.click.uz/pay?id=0105991&t=0"

EXAM_LOCATION_LAT = 41.29872833124857
EXAM_LOCATION_LON = 69.34990462234283

# client_id -> [(admin_id, message_id), ...] — сообщения с кнопкой у админов
SENT_TO_ADMINS: dict[int, list[tuple[int, int]]] = {}
# client_id -> имя админа, который подтвердил
CLAIMED: dict[int, str] = {}


class ExamFlow(StatesGroup):
    waiting_passport = State()
    waiting_receipt = State()


def confirm_keyboard(client_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"confirm_{client_id}",
            )
        ]]
    )


def done_keyboard(admin_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=f"✅ Подтвердил {admin_name}",
                callback_data="noop",
            )
        ]]
    )


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Sizni sertifikat olish uchun rus tili imtihoniga yozilish qiziqtiryaptimi?\n\n"
        "Imtihon Toshkentda o'tkaziladi.\n"
        "Yozilish narxi: 1 400 000 so'm.\n\n"
        "Davom etish va bo'sh sanalarni bilish uchun 'ha' deb yozing."
    )

    voice = FSInputFile("greeting.ogg")
    await message.answer_voice(voice)


@dp.message(F.text.lower() == "ha")
async def show_dates(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=date, callback_data=f"date_{date}")]
            for date in EXAM_DATES
        ]
    )
    await message.answer("Imtihon uchun qulay sanani tanlang:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    chosen_date = callback.data.replace("date_", "")
    await state.update_data(exam_date=chosen_date)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(
        f"Siz {chosen_date} sanasini tanladingiz ✅\n\n"
        "Yozilishni yakunlash uchun, iltimos, chet el pasportingiz rasmini yuboring."
    )
    await callback.answer()


@dp.message(StateFilter(ExamFlow.waiting_passport), F.photo | F.document)
async def passport_handler(message: Message, state: FSMContext):
    await state.set_state(ExamFlow.waiting_receipt)
    await message.answer(
        "Rahmat! Pasport qabul qilindi. 📄\n\n"
        "To'lov uchun quyidagi havolalardan birini ishlating:\n\n"
        f"💳 Payme: {PAYME_LINK}\n"
        f"💳 Click: {CLICK_LINK}\n\n"
        "To'lovdan so'ng, iltimos, chekning skrinshotini yuboring."
    )


@dp.message(StateFilter(ExamFlow.waiting_receipt), F.photo | F.document)
async def receipt_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    exam_date = data.get("exam_date", "не указана")
    client_id = message.from_user.id

    await message.answer(
        "Rahmat! Chek qabul qilindi. ⏳\n\n"
        "Administrator tasdiqlashini kuting."
    )

    username = message.from_user.username
    caption = (
        f"Чек от клиента: {message.from_user.full_name}"
        f"{' (@' + username + ')' if username else ''}\n"
        f"ID: {client_id}\n"
        f"Дата экзамена: {exam_date}"
    )

    SENT_TO_ADMINS[client_id] = []
    CLAIMED.pop(client_id, None)

    for admin_id in ADMIN_IDS:
        try:
            await bot.forward_message(admin_id, message.chat.id, message.message_id)
            sent = await bot.send_message(
                admin_id, caption, reply_markup=confirm_keyboard(client_id)
            )
            SENT_TO_ADMINS[client_id].append((admin_id, sent.message_id))
        except Exception as e:
            print(f"[admins] не доставлено админу {admin_id}: {e}")

    await state.clear()


@dp.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    client_id = int(callback.data.replace("confirm_", ""))

    if client_id in CLAIMED:
        await callback.answer(
            f"Заявку уже подтвердил {CLAIMED[client_id]}.", show_alert=True
        )
        return

    admin_name = callback.from_user.full_name
    CLAIMED[client_id] = admin_name
    await callback.answer("Подтверждено")

    # убираем кнопку у всех админов, включая нажавшего
    for admin_id, message_id in SENT_TO_ADMINS.get(client_id, []):
        try:
            await bot.edit_message_reply_markup(
                chat_id=admin_id,
                message_id=message_id,
                reply_markup=done_keyboard(admin_name),
            )
        except Exception as e:
            print(f"[admins] не удалось обновить сообщение у {admin_id}: {e}")
    SENT_TO_ADMINS.pop(client_id, None)

    try:
        await bot.send_message(
            client_id,
            "To'lov tasdiqlandi! ✅\n\n"
            "Siz uchun imtihonda joy band qilindi.\n\n"
            "📍 Imtihon o'tkaziladigan joy:"
        )
        await bot.send_location(
            client_id, latitude=EXAM_LOCATION_LAT, longitude=EXAM_LOCATION_LON
        )
    except Exception as e:
        print(f"[client] не удалось уведомить {client_id}: {e}")
        await callback.message.answer(f"⚠️ Клиенту не доставлено: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
