import os
import asyncio
import aiosqlite
from datetime import datetime
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
DB_PATH = os.environ.get("DB_PATH", "bot.db")


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

DEFAULT_DATES = ["15 sentabr", "22 sentabr", "29 sentabr"]
PAYME_LINK = "https://payme.uz/fallback/merchant/?id=6a4673b9ccf9c1de0aa04520"
CLICK_LINK = "https://indoor.click.uz/pay?id=0105991&t=0"

EXAM_LOCATION_LAT = 41.29872833124857
EXAM_LOCATION_LON = 69.34990462234283


# ---------- БАЗА ----------

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exam_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                seats_limit INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT,
                username TEXT,
                date_id INTEGER NOT NULL,
                passport_file_id TEXT,
                receipt_file_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                confirmed_by INTEGER,
                confirmed_by_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (date_id) REFERENCES exam_dates(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                booking_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                PRIMARY KEY (booking_id, admin_id)
            )
        """)
        # первичное заполнение датами
        cur = await db.execute("SELECT COUNT(*) FROM exam_dates")
        (count,) = await cur.fetchone()
        if count == 0:
            for i, title in enumerate(DEFAULT_DATES):
                await db.execute(
                    "INSERT INTO exam_dates (title, seats_limit, sort_order) VALUES (?, ?, ?)",
                    (title, 0, i),
                )
        await db.commit()
    print(f"[db] готова: {DB_PATH}")


async def get_active_dates() -> list[tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title FROM exam_dates WHERE is_active = 1 ORDER BY sort_order, id"
        )
        return await cur.fetchall()


async def get_date_title(date_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT title FROM exam_dates WHERE id = ?", (date_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указана"


async def has_active_booking(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM bookings WHERE user_id = ? AND status IN ('pending','confirmed')",
            (user_id,),
        )
        return await cur.fetchone() is not None


async def create_booking(
    user_id: int, full_name: str, username: str, date_id: int,
    passport_file_id: str, receipt_file_id: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO bookings
               (user_id, full_name, username, date_id, passport_file_id,
                receipt_file_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (user_id, full_name, username, date_id, passport_file_id,
             receipt_file_id, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cur.lastrowid


async def save_admin_message(booking_id: int, admin_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admin_messages VALUES (?, ?, ?)",
            (booking_id, admin_id, message_id),
        )
        await db.commit()


async def get_admin_messages(booking_id: int) -> list[tuple[int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT admin_id, message_id FROM admin_messages WHERE booking_id = ?",
            (booking_id,),
        )
        return await cur.fetchall()


async def claim_booking(booking_id: int, admin_id: int, admin_name: str):
    """Возвращает (успех, user_id, имя_подтвердившего)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE bookings
               SET status = 'confirmed', confirmed_by = ?, confirmed_by_name = ?
               WHERE id = ? AND status = 'pending'""",
            (admin_id, admin_name, booking_id),
        )
        await db.commit()
        won = cur.rowcount > 0

        cur = await db.execute(
            "SELECT user_id, confirmed_by_name FROM bookings WHERE id = ?",
            (booking_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False, None, None
        return won, row[0], row[1]


# ---------- БОТ ----------

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
    await message.answer_voice(FSInputFile("greeting.ogg"))


@dp.message(F.text.lower() == "ha")
async def show_dates(message: Message):
    if await has_active_booking(message.from_user.id):
        await message.answer(
            "Siz allaqachon imtihonga yozilgansiz. ✅\n"
            "Savollar bo'lsa, administrator bilan bog'laning."
        )
        return

    dates = await get_active_dates()
    if not dates:
        await message.answer("Hozircha bo'sh sanalar yo'q. Keyinroq urinib ko'ring.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title, callback_data=f"date_{date_id}")]
        for date_id, title in dates
    ])
    await message.answer("Imtihon uchun qulay sanani tanlang:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    date_id = int(callback.data.replace("date_", ""))
    title = await get_date_title(date_id)

    await state.update_data(date_id=date_id, date_title=title)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(
        f"Siz {title} sanasini tanladingiz ✅\n\n"
        "Yozilishni yakunlash uchun, iltimos, chet el pasportingiz rasmini yuboring."
    )
    await callback.answer()


@dp.message(StateFilter(ExamFlow.waiting_passport), F.photo | F.document)
async def passport_handler(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await state.update_data(passport_file_id=file_id)
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
    date_id = data.get("date_id")
    date_title = data.get("date_title", "не указана")
    user = message.from_user

    receipt_file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    booking_id = await create_booking(
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

    for admin_id in ADMIN_IDS:
        try:
            await bot.forward_message(admin_id, message.chat.id, message.message_id)
            sent = await bot.send_message(
                admin_id, caption, reply_markup=confirm_keyboard(booking_id)
            )
            await save_admin_message(booking_id, admin_id, sent.message_id)
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

    booking_id = int(callback.data.replace("confirm_", ""))
    admin_name = callback.from_user.full_name

    won, client_id, winner_name = await claim_booking(
        booking_id, callback.from_user.id, admin_name
    )

    if client_id is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if not won:
        await callback.answer(f"Заявку уже подтвердил {winner_name}.", show_alert=True)
        return

    await callback.answer("Подтверждено")

    for admin_id, message_id in await get_admin_messages(booking_id):
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
            client_id, latitude=EXAM_LOCATION_LAT, longitude=EXAM_LOCATION_LON
        )
    except Exception as e:
        print(f"[client] не удалось уведомить {client_id}: {e}")
        await callback.message.answer(f"⚠️ Клиенту не доставлено: {e}")


async def main():
    await db_init()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
