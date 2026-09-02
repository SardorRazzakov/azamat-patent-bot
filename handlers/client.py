from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import db

router = Router(name="client")


class ExamFlow(StatesGroup):
    waiting_passport = State()
    waiting_receipt = State()


def confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Подтвердить оплату",
            callback_data=f"confirm_{booking_id}",
        )
    ]])


def done_keyboard(admin_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"✅ Подтвердил {admin_name}", callback_data="noop")
    ]])


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Sizni sertifikat olish uchun rus tili imtihoniga yozilish qiziqtiryaptimi?\n\n"
        "Imtihon Toshkentda o'tkaziladi.\n"
        "Yozilish narxi: 1 400 000 so'm.\n\n"
        "Davom etish va bo'sh sanalarni bilish uchun 'ha' deb yozing."
    )
    await message.answer_voice(FSInputFile(config.GREETING_VOICE))


@router.message(F.text.lower() == "ha")
async def show_dates(message: Message):
    if await db.has_active_booking(message.from_user.id):
        await message.answer(
            "Siz allaqachon imtihonga yozilgansiz. ✅\n"
            "Savollar bo'lsa, administrator bilan bog'laning."
        )
        return

    dates = await db.get_bookable_dates()
    if not dates:
        await message.answer("Hozircha bo'sh sanalar yo'q. Keyinroq urinib ko'ring.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title, callback_data=f"date_{date_id}")]
        for date_id, title in dates
    ])
    await message.answer("Imtihon uchun qulay sanani tanlang:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    date_id = int(callback.data.replace("date_", ""))

    if not await db.is_date_bookable(date_id):
        await callback.answer(
            "Bu sanada bo'sh joy qolmadi. Boshqa sanani tanlang.", show_alert=True
        )
        return

    title = await db.get_date_title(date_id)

    await state.update_data(date_id=date_id, date_title=title)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(
        f"Siz {title} sanasini tanladingiz ✅\n\n"
        "Yozilishni yakunlash uchun, iltimos, chet el pasportingiz rasmini yuboring."
    )
    await callback.answer()


@router.message(StateFilter(ExamFlow.waiting_passport), F.photo | F.document)
async def passport_handler(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await state.update_data(passport_file_id=file_id)
    await state.set_state(ExamFlow.waiting_receipt)
    await message.answer(
        "Rahmat! Pasport qabul qilindi. 📄\n\n"
        "To'lov uchun quyidagi havolalardan birini ishlating:\n\n"
        f"💳 Payme: {config.PAYME_LINK}\n"
        f"💳 Click: {config.CLICK_LINK}\n\n"
        "To'lovdan so'ng, iltimos, chekning skrinshotini yuboring."
    )


@router.message(StateFilter(ExamFlow.waiting_receipt), F.photo | F.document)
async def receipt_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    date_id = data.get("date_id")
    date_title = data.get("date_title", "не указана")
    user = message.from_user

    receipt_file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    booking_id = await db.create_booking(
        user.id, user.full_name, user.username or "",
        date_id, data.get("passport_file_id", ""), receipt_file_id,
    )

    await message.answer(
        "Rahmat! Chek qabul qilindi. ⏳\n\nAdministrator tasdiqlashini kuting."
    )

    caption = (
        f"Заявка №{booking_id}\n"
        f"Клиент: {user.full_name}"
        f"{' (@' + user.username + ')' if user.username else ''}\n"
        f"ID: {user.id}\n"
        f"Дата экзамена: {date_title}"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.forward_message(admin_id, message.chat.id, message.message_id)
            sent = await bot.send_message(
                admin_id, caption, reply_markup=confirm_keyboard(booking_id)
            )
            await db.save_admin_message(booking_id, admin_id, sent.message_id)
        except Exception as e:
            print(f"[admins] не доставлено админу {admin_id}: {e}")

    await state.clear()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    booking_id = int(callback.data.replace("confirm_", ""))
    admin_name = callback.from_user.full_name

    won, client_id, winner_name = await db.claim_booking(
        booking_id, callback.from_user.id, admin_name
    )

    if client_id is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if not won:
        await callback.answer(f"Заявку уже подтвердил {winner_name}.", show_alert=True)
        return

    await callback.answer("Подтверждено")

    for admin_id, message_id in await db.get_admin_messages(booking_id):
        try:
            await bot.edit_message_reply_markup(
                chat_id=admin_id,
                message_id=message_id,
                reply_markup=done_keyboard(admin_name),
            )
        except Exception as e:
            print(f"[admins] не удалось обновить сообщение у {admin_id}: {e}")

    try:
        await bot.send_message(
            client_id,
            "To'lov tasdiqlandi! ✅\n\n"
            "Siz uchun imtihonda joy band qilindi.\n\n"
            "📍 Imtihon o'tkaziladigan joy:"
        )
        await bot.send_location(
            client_id,
            latitude=config.EXAM_LOCATION_LAT,
            longitude=config.EXAM_LOCATION_LON,
        )
    except Exception as e:
        print(f"[client] не удалось уведомить {client_id}: {e}")
        await callback.message.answer(f"⚠️ Клиенту не доставлено: {e}")
