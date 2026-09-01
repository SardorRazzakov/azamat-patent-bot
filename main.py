import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

EXAM_DATES = ["15 sentabr", "22 sentabr", "29 sentabr"]
PAYME_LINK = "https://payme.uz/fallback/merchant/?id=6a4673b9ccf9c1de0aa04520"
CLICK_LINK = "https://indoor.click.uz/pay?id=0105991&t=0"

EXAM_LOCATION_LAT = 41.29872833124857
EXAM_LOCATION_LON = 69.34990462234283

class ExamFlow(StatesGroup):
    waiting_passport = State()
    waiting_receipt = State()

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
async def date_chosen(callback, state: FSMContext):
    chosen_date = callback.data.replace("date_", "")
    await state.update_data(exam_date=chosen_date)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(
        f"Siz {chosen_date} sanasini tanladingiz ✅\n\n"
        "Yozilishni yakunlash uchun, iltimos, chet el pasporti rasmini yuboring."
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

    await message.answer(
        "Rahmat! Chek qabul qilindi. ⏳\n\n"
        "Administrator tasdiqlashini kuting."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"confirm_{message.from_user.id}"
            )
        ]]
    )
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    await bot.send_message(
        ADMIN_ID,
        f"Чек от клиента: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"Дата экзамена: {exam_date}",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback):
    client_id = int(callback.data.replace("confirm_", ""))

    await bot.send_message(
        client_id,
        "To'lov tasdiqlandi! ✅\n\n"
        "Siz uchun imtihonda joy band qilindi.\n\n"
        "📍 Imtihon o'tkaziladigan joy:"
    )
    await bot.send_location(client_id, latitude=EXAM_LOCATION_LAT, longitude=EXAM_LOCATION_LON)

    await callback.message.answer("Клиент уведомлён, локация отправлена ✅")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
