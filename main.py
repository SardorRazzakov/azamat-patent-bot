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

EXAM_DATES = ["15 сентября", "22 сентября", "29 сентября"]
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
        "Здравствуйте! 👋\n\n"
        "Вас интересует запись на экзамен по русскому языку для получения сертификата?\n\n"
        "Экзамен проводится в Ташкенте.\n"
        "Стоимость записи: 1 400 000 сум.\n\n"
        "Напишите 'да', чтобы продолжить и узнать свободные даты."
    )

    voice = FSInputFile("greeting.ogg")
    await message.answer_voice(voice)

@dp.message(F.text.lower() == "да")
async def show_dates(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=date, callback_data=f"date_{date}")]
            for date in EXAM_DATES
        ]
    )
    await message.answer("Выберите удобную дату экзамена:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("date_"))
async def date_chosen(callback, state: FSMContext):
    chosen_date = callback.data.replace("date_", "")
    await state.update_data(exam_date=chosen_date)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(
        f"Вы выбрали дату: {chosen_date} ✅\n\n"
        "Для завершения записи, пожалуйста, отправьте фото загранпаспорта."
    )
    await callback.answer()

@dp.message(StateFilter(ExamFlow.waiting_passport), F.photo | F.document)
async def passport_handler(message: Message, state: FSMContext):
    await state.set_state(ExamFlow.waiting_receipt)
    await message.answer(
        "Спасибо! Паспорт получен. 📄\n\n"
        "Для оплаты записи используйте одну из ссылок:\n\n"
        f"💳 Payme: {PAYME_LINK}\n"
        f"💳 Click: {CLICK_LINK}\n\n"
        "После оплаты пришлите, пожалуйста, скриншот чека."
    )

@dp.message(StateFilter(ExamFlow.waiting_receipt), F.photo | F.document)
async def receipt_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    exam_date = data.get("exam_date", "не указана")

    await message.answer(
        "Спасибо! Чек получен. ⏳\n\n"
        "Ожидайте подтверждения от администратора."
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
        "Оплата подтверждена! ✅\n\n"
        "За вами забронировано место на экзамен.\n\n"
        "📍 Локация проведения экзамена:"
    )
    await bot.send_location(client_id, latitude=EXAM_LOCATION_LAT, longitude=EXAM_LOCATION_LON)

    await callback.message.answer("Клиент уведомлён, локация отправлена ✅")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
