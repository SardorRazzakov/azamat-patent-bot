from contextlib import suppress
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

import config
import db
import texts

router = Router(name="client")


class LanguageMiddleware(BaseMiddleware):
    """Кладёт язык клиента в data, чтобы хендлеры не ходили за ним сами."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        stored = await db.get_user_lang(user.id) if user else None
        data["lang"] = texts.lang_or_default(stored)
        return await handler(event, data)


router.message.middleware(LanguageMiddleware())
router.callback_query.middleware(LanguageMiddleware())


class ExamFlow(StatesGroup):
    waiting_applicant = State()
    waiting_passport = State()
    waiting_receipt = State()


# ---------- КЛАВИАТУРЫ ----------

def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=texts.LANGUAGE_NAMES[code], callback_data=f"lang:{code}"
        )]
        for code in texts.LANGUAGES
    ])


def continue_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=texts.t("btn_continue", lang), callback_data="go:dates"
        )
    ]])


def add_more_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=texts.t("btn_add_more", lang), callback_data="go:more"
        )
    ]])


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


# ---------- ВЫБОР ЯЗЫКА ----------

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    """Доступна в любой момент: сбрасывает состояние и даёт сменить язык."""
    await state.clear()
    await db.log_event(message.from_user.id, db.STEP_START)
    await message.answer(texts.CHOOSE_LANGUAGE, reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    if code not in texts.LANGUAGES:
        await callback.answer()
        return

    await state.clear()
    await db.set_user_lang(callback.from_user.id, code)
    await db.log_event(callback.from_user.id, db.STEP_LANG)

    # Язык из middleware здесь ещё прежний, поэтому дальше только code.
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"{texts.CHOOSE_LANGUAGE}\n\n{texts.LANGUAGE_NAMES[code]} ✅"
        )

    await callback.message.answer(
        texts.t("greeting", code), reply_markup=continue_keyboard(code)
    )
    await callback.message.answer_voice(FSInputFile(config.GREETING_VOICE))
    await callback.answer()


# ---------- ЗАПИСЬ НА ЭКЗАМЕН ----------

async def send_dates(message: Message, lang: str) -> bool:
    """Показывает список дат. False — показывать нечего."""
    dates = await db.get_bookable_dates()
    if not dates:
        await message.answer(texts.t("no_dates", lang))
        return False

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title, callback_data=f"date_{date_id}")]
        for date_id, title in dates
    ])
    await message.answer(texts.t("choose_date", lang), reply_markup=keyboard)
    return True


@router.callback_query(F.data == "go:dates")
async def show_dates(callback: CallbackQuery, lang: str):
    if await db.has_active_booking(callback.from_user.id):
        # не тупик: с одного аккаунта часто записывают друзей, поэтому
        # сразу предлагаем оформить заявку на другого человека
        await callback.message.answer(
            texts.t("already_booked", lang), reply_markup=add_more_keyboard(lang)
        )
        await callback.answer()
        return

    await send_dates(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "go:more")
async def add_more_start(callback: CallbackQuery, state: FSMContext, lang: str):
    """Запись друга с того же аккаунта. Проверку на «уже записан» здесь
    не делаем осознанно: заявка оформляется на другого человека."""
    await state.clear()
    await state.set_state(ExamFlow.waiting_applicant)
    await callback.message.answer(texts.t("ask_applicant_name", lang))
    await callback.answer()


@router.message(StateFilter(ExamFlow.waiting_applicant), F.text)
async def applicant_name_received(message: Message, state: FSMContext, lang: str):
    name = message.text.strip()
    if not name:
        await message.answer(texts.t("ask_applicant_name", lang))
        return

    await state.update_data(applicant_name=name[:100])
    if not await send_dates(message, lang):
        await state.clear()


@router.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext, lang: str):
    date_id = int(callback.data.replace("date_", ""))

    if not await db.is_date_bookable(date_id):
        await callback.answer(texts.t("date_full", lang), show_alert=True)
        return

    title = await db.get_date_title(date_id)

    await db.log_event(callback.from_user.id, db.STEP_DATE)
    await state.update_data(date_id=date_id, date_title=title)
    await state.set_state(ExamFlow.waiting_passport)
    await callback.message.answer(texts.t("date_chosen", lang, title=title))
    await callback.answer()


@router.message(StateFilter(ExamFlow.waiting_passport), F.photo | F.document)
async def passport_handler(message: Message, state: FSMContext, lang: str):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await state.update_data(passport_file_id=file_id)
    await state.set_state(ExamFlow.waiting_receipt)
    await db.log_event(message.from_user.id, db.STEP_PASSPORT)
    await message.answer(texts.t(
        "passport_received", lang,
        payme=config.PAYME_LINK, click=config.CLICK_LINK,
    ))


@router.message(StateFilter(ExamFlow.waiting_receipt), F.photo | F.document)
async def receipt_handler(message: Message, state: FSMContext, lang: str, bot: Bot):
    data = await state.get_data()
    date_id = data.get("date_id")
    date_title = data.get("date_title", "не указана")
    user = message.from_user

    receipt_file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    applicant_name = data.get("applicant_name")

    booking_id = await db.create_booking(
        user.id, user.full_name, user.username or "",
        date_id, data.get("passport_file_id", ""), receipt_file_id,
        applicant_name,
    )
    # место могло уйти, пока клиент платил: проверка идёт в одной
    # транзакции со вставкой, поэтому здесь возможен None
    if booking_id is None:
        await state.clear()
        await message.answer(texts.t("seat_gone", lang))
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ Место уже занято: {user.full_name} (ID {user.id}) "
                    f"оплатил и прислал чек на дату «{date_title}», "
                    f"но свободных мест не осталось.",
                )
            except Exception as e:
                print(f"[admins] не доставлено админу {admin_id}: {e}")
        return

    await db.log_event(user.id, db.STEP_RECEIPT)
    await message.answer(
        texts.t("receipt_received", lang), reply_markup=add_more_keyboard(lang)
    )

    caption = (
        f"Заявка №{booking_id}\n"
        f"Клиент: {user.full_name}"
        f"{' (@' + user.username + ')' if user.username else ''}\n"
        f"ID: {user.id}\n"
        + (f"Записан: {applicant_name}\n" if applicant_name else "")
        + f"Дата экзамена: {date_title}"
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


# ---------- ПОДТВЕРЖДЕНИЕ ОПЛАТЫ (нажимает админ) ----------

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

    await db.log_event(client_id, db.STEP_PAID)

    # Язык клиента, а не того админа, который нажал кнопку.
    client_lang = texts.lang_or_default(await db.get_user_lang(client_id))
    try:
        await bot.send_message(client_id, texts.t("payment_confirmed", client_lang))
        await bot.send_location(
            client_id,
            latitude=config.EXAM_LOCATION_LAT,
            longitude=config.EXAM_LOCATION_LON,
        )
    except Exception as e:
        print(f"[client] не удалось уведомить {client_id}: {e}")
        await callback.message.answer(f"⚠️ Клиенту не доставлено: {e}")


# ---------- ПОДСКАЗКИ НА НЕОЖИДАННЫЙ ВВОД ----------
# Идут последними: перехватывают всё, что не разобрали хендлеры выше.

@router.message(StateFilter(ExamFlow.waiting_passport))
async def passport_expected(message: Message, lang: str):
    await message.answer(texts.t("need_passport", lang))


@router.message(StateFilter(ExamFlow.waiting_receipt))
async def receipt_expected(message: Message, lang: str):
    await message.answer(texts.t("need_receipt", lang))


@router.message()
async def unexpected_message(message: Message, lang: str):
    await message.answer(
        texts.t("fallback", lang), reply_markup=continue_keyboard(lang)
    )
