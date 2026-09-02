from datetime import datetime, timezone
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

import config
import db
import texts

PAGE_SIZE = 8

# Ввод в FSM-шагах: любой текст, кроме команд. Иначе /start и прочие
# команды попали бы в название даты вместо того, чтобы сработать.
PLAIN_TEXT = F.text & ~F.text.startswith("/")

STATUS_ICON = {db.PENDING: "⏳", db.CONFIRMED: "✅", db.CANCELLED: "❌"}
STATUS_TEXT = {
    db.PENDING: "ждёт подтверждения",
    db.CONFIRMED: "подтверждена",
    db.CANCELLED: "отменена",
}


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and event.from_user.id in config.ADMIN_IDS


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AdminFlow(StatesGroup):
    date_title = State()
    date_limit_new = State()
    date_limit_edit = State()
    date_title_edit = State()


# ---------- ХЕЛПЕРЫ ----------

def fmt_dt(raw: str | None) -> str:
    """created_at лежит в базе в UTC, показываем в ташкентском времени.

    Заявки, созданные до перехода на timezone-aware время, записаны через
    utcnow() и лежат без смещения — их тоже считаем UTC.
    """
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw[:19].replace("T", " ")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(config.TZ).strftime("%d.%m.%Y %H:%M")


def fmt_limit(seats_limit: int) -> str:
    return str(seats_limit) if seats_limit else "без лимита"


def back_button(callback_data: str, text: str = "⬅️ Назад") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


async def show(callback: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup):
    """Перерисовывает экран админки на месте; если нельзя — шлёт новым сообщением."""
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Даты", callback_data="a:dates")],
        [InlineKeyboardButton(text="👥 Записавшиеся", callback_data="a:bdates")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="a:stats")],
        [InlineKeyboardButton(text="📥 Экспорт в Excel", callback_data="a:export")],
    ])


MENU_TEXT = "🛠 Админ-панель\n\nВыберите раздел:"


# ---------- ВХОД ----------

@router.message(Command("admin"))
async def admin_entry(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MENU_TEXT, reply_markup=menu_keyboard())


@router.message(Command("cancel"))
async def admin_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Отменено.", reply_markup=menu_keyboard())


@router.callback_query(F.data == "a:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(callback, MENU_TEXT, menu_keyboard())
    await callback.answer()


# ---------- ДАТЫ ----------

async def render_dates(callback: CallbackQuery):
    dates = await db.get_dates_overview()

    rows = []
    for date_id, title, seats_limit, is_active, confirmed, pending in dates:
        taken = confirmed + pending
        seats = f"{taken}/{seats_limit}" if seats_limit else f"{taken}"
        mark = "" if is_active else "🚫 "
        rows.append([InlineKeyboardButton(
            text=f"{mark}{title} — {seats}", callback_data=f"a:d:{date_id}"
        )])

    rows.append([InlineKeyboardButton(text="➕ Добавить дату", callback_data="a:dadd")])
    rows.append([back_button("a:menu", "⬅️ В меню")])

    text = "📅 Даты экзамена\n\nВ кнопках — занято мест (записи в ожидании + подтверждённые)."
    if not dates:
        text = "📅 Даты экзамена\n\nПока ни одной даты нет."

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "a:dates")
async def dates_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_dates(callback)
    await callback.answer()


async def render_date_detail(callback: CallbackQuery, date_id: int) -> bool:
    row = await db.get_date_overview(date_id)
    if not row:
        await render_dates(callback)
        return False

    _, title, seats_limit, is_active, confirmed, pending = row
    taken = confirmed + pending
    free = "—" if not seats_limit else max(seats_limit - taken, 0)

    text = (
        f"📅 {title}\n\n"
        f"Статус: {'активна' if is_active else 'скрыта из записи'}\n"
        f"Лимит мест: {fmt_limit(seats_limit)}\n"
        f"Свободно: {free}\n\n"
        f"✅ Подтверждено: {confirmed}\n"
        f"⏳ Ждут подтверждения: {pending}"
    )

    rows = [
        [InlineKeyboardButton(
            text="👥 Записавшиеся", callback_data=f"a:bk:{date_id}:0"
        )],
        [InlineKeyboardButton(
            text="🔢 Изменить лимит", callback_data=f"a:dlim:{date_id}"
        )],
        [InlineKeyboardButton(
            text="✏️ Переименовать", callback_data=f"a:dren:{date_id}"
        )],
    ]
    if is_active:
        rows.append([InlineKeyboardButton(
            text="🗑 Удалить дату", callback_data=f"a:ddel:{date_id}"
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="♻️ Вернуть в запись", callback_data=f"a:drst:{date_id}"
        )])
    rows.append([back_button("a:dates")])

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    return True


@router.callback_query(F.data.startswith("a:d:"))
async def date_detail(callback: CallbackQuery):
    date_id = int(callback.data.split(":")[2])
    if await render_date_detail(callback, date_id):
        await callback.answer()
    else:
        await callback.answer("Дата не найдена.", show_alert=True)


@router.callback_query(F.data == "a:dadd")
async def date_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.date_title)
    await show(
        callback,
        "➕ Новая дата\n\n"
        "Пришлите название так, как его увидит клиент (например: 6 oktabr).\n\n"
        "/cancel — отмена",
        InlineKeyboardMarkup(inline_keyboard=[[back_button("a:dates", "⬅️ Отмена")]]),
    )
    await callback.answer()


@router.message(AdminFlow.date_title, PLAIN_TEXT)
async def date_add_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз.")
        return

    await state.update_data(title=title)
    await state.set_state(AdminFlow.date_limit_new)
    await message.answer(
        f"Название: {title}\n\n"
        "Теперь пришлите лимит мест числом. 0 — без лимита.\n\n"
        "/cancel — отмена"
    )


@router.message(AdminFlow.date_limit_new, PLAIN_TEXT)
async def date_add_limit(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Нужно целое число (0 — без лимита).")
        return

    seats_limit = int(message.text.strip())
    data = await state.get_data()
    await state.clear()

    date_id = await db.add_date(data["title"], seats_limit)
    if date_id is None:
        await message.answer(
            f"Дата «{data['title']}» уже есть в списке.",
            reply_markup=menu_keyboard(),
        )
        return

    await message.answer(
        f"✅ Дата «{data['title']}» добавлена. Лимит мест: {fmt_limit(seats_limit)}.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К списку дат", callback_data="a:dates")],
            [back_button("a:menu", "⬅️ В меню")],
        ]),
    )


@router.callback_query(F.data.startswith("a:dlim:"))
async def date_limit_start(callback: CallbackQuery, state: FSMContext):
    date_id = int(callback.data.split(":")[2])
    row = await db.get_date_overview(date_id)
    if not row:
        await callback.answer("Дата не найдена.", show_alert=True)
        return

    _, title, seats_limit, _, confirmed, pending = row
    await state.set_state(AdminFlow.date_limit_edit)
    await state.update_data(date_id=date_id)

    await show(
        callback,
        f"✏️ Лимит мест для «{title}»\n\n"
        f"Сейчас: {fmt_limit(seats_limit)}\n"
        f"Уже занято: {confirmed + pending}\n\n"
        "Пришлите новый лимит числом. 0 — без лимита.\n\n"
        "/cancel — отмена",
        InlineKeyboardMarkup(inline_keyboard=[
            [back_button(f"a:d:{date_id}", "⬅️ Отмена")]
        ]),
    )
    await callback.answer()


@router.message(AdminFlow.date_limit_edit, PLAIN_TEXT)
async def date_limit_save(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Нужно целое число (0 — без лимита).")
        return

    seats_limit = int(message.text.strip())
    data = await state.get_data()
    date_id = data["date_id"]
    await state.clear()

    await db.set_date_limit(date_id, seats_limit)
    row = await db.get_date_overview(date_id)
    title = row[1] if row else f"#{date_id}"

    await message.answer(
        f"✅ Лимит для «{title}» — {fmt_limit(seats_limit)}.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К дате", callback_data=f"a:d:{date_id}")],
            [back_button("a:menu", "⬅️ В меню")],
        ]),
    )


@router.callback_query(F.data.startswith("a:dren:"))
async def date_rename_start(callback: CallbackQuery, state: FSMContext):
    date_id = int(callback.data.split(":")[2])
    row = await db.get_date_overview(date_id)
    if not row:
        await callback.answer("Дата не найдена.", show_alert=True)
        return

    title = row[1]
    await state.set_state(AdminFlow.date_title_edit)
    await state.update_data(date_id=date_id)

    await show(
        callback,
        f"✏️ Переименование даты «{title}»\n\n"
        "Пришлите новое название так, как его увидит клиент.\n"
        "Заявки и лимит останутся на месте.\n\n"
        "/cancel — отмена",
        InlineKeyboardMarkup(inline_keyboard=[
            [back_button(f"a:d:{date_id}", "⬅️ Отмена")]
        ]),
    )
    await callback.answer()


@router.message(AdminFlow.date_title_edit, PLAIN_TEXT)
async def date_rename_save(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Пришлите другое.")
        return

    data = await state.get_data()
    date_id = data["date_id"]
    result = await db.rename_date(date_id, title)

    if result == "duplicate":
        # состояние не сбрасываем — админ может сразу прислать другое название
        await message.answer(f"Дата «{title}» уже есть в списке. Пришлите другое название.")
        return

    await state.clear()

    if result == "missing":
        await message.answer("Дата не найдена — похоже, её успели удалить.",
                             reply_markup=menu_keyboard())
        return

    await message.answer(
        f"✅ Новое название: «{title}».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К дате", callback_data=f"a:d:{date_id}")],
            [back_button("a:menu", "⬅️ В меню")],
        ]),
    )


@router.callback_query(F.data.startswith("a:ddel:"))
async def date_delete_confirm(callback: CallbackQuery):
    date_id = int(callback.data.split(":")[2])
    row = await db.get_date_overview(date_id)
    if not row:
        await callback.answer("Дата не найдена.", show_alert=True)
        return

    _, title, _, _, confirmed, pending = row
    total = confirmed + pending

    text = f"🗑 Удалить дату «{title}»?"
    if total:
        text += (
            f"\n\nПо ней уже есть заявки ({total}). Дата будет скрыта из записи, "
            "а заявки и история останутся."
        )

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"a:ddel1:{date_id}")],
        [back_button(f"a:d:{date_id}", "⬅️ Отмена")],
    ]))
    await callback.answer()


@router.callback_query(F.data.startswith("a:ddel1:"))
async def date_delete_do(callback: CallbackQuery):
    date_id = int(callback.data.split(":")[2])
    result = await db.delete_date(date_id)
    await callback.answer("Удалено" if result == "deleted" else "Дата скрыта из записи")
    await render_dates(callback)


@router.callback_query(F.data.startswith("a:drst:"))
async def date_restore(callback: CallbackQuery):
    date_id = int(callback.data.split(":")[2])
    await db.restore_date(date_id)
    await callback.answer("Дата снова доступна для записи")
    await render_date_detail(callback, date_id)


# ---------- ЗАПИСАВШИЕСЯ ----------

@router.callback_query(F.data == "a:bdates")
async def bookings_dates(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    dates = await db.get_dates_overview()

    rows = [
        [InlineKeyboardButton(
            text=f"{title} — {confirmed + pending}", callback_data=f"a:bk:{date_id}:0"
        )]
        for date_id, title, _, _, confirmed, pending in dates
    ]
    rows.append([back_button("a:menu", "⬅️ В меню")])

    text = "👥 Записавшиеся\n\nВыберите дату:"
    if not dates:
        text = "👥 Записавшиеся\n\nДат пока нет."

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("a:bk:"))
async def bookings_list(callback: CallbackQuery):
    _, _, raw_date_id, raw_page = callback.data.split(":")
    date_id, page = int(raw_date_id), int(raw_page)

    date_row = await db.get_date_overview(date_id)
    title = date_row[1] if date_row else f"#{date_id}"
    bookings = await db.get_bookings_for_date(date_id)

    if not bookings:
        await show(callback, f"👥 {title}\n\nЗаписей пока нет.", InlineKeyboardMarkup(
            inline_keyboard=[[back_button(f"a:d:{date_id}")]]
        ))
        await callback.answer()
        return

    pages = (len(bookings) - 1) // PAGE_SIZE + 1
    page = max(0, min(page, pages - 1))
    chunk = bookings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    rows = []
    for booking_id, full_name, username, _, status, _, _ in chunk:
        icon = STATUS_ICON.get(status, "•")
        name = full_name or (f"@{username}" if username else "без имени")
        name = name[:32]
        rows.append([InlineKeyboardButton(
            text=f"{icon} №{booking_id} {name}", callback_data=f"a:b:{booking_id}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"a:bk:{date_id}:{page - 1}"
        ))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(
            text="➡️", callback_data=f"a:bk:{date_id}:{page + 1}"
        ))
    if nav:
        rows.append(nav)
    rows.append([back_button(f"a:d:{date_id}")])

    text = (
        f"👥 {title}\n"
        f"Всего записей: {len(bookings)}"
        + (f"   ·   стр. {page + 1}/{pages}" if pages > 1 else "")
        + "\n\n✅ подтверждена   ⏳ ждёт   ❌ отменена"
    )

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


async def render_booking_detail(callback: CallbackQuery, booking_id: int) -> bool:
    row = await db.get_booking(booking_id)
    if not row:
        return False

    (_, user_id, full_name, username, date_id, status,
     confirmed_by_name, created_at, date_title) = row

    text = (
        f"Заявка №{booking_id}\n\n"
        f"Клиент: {full_name or '—'}"
        f"{' (@' + username + ')' if username else ''}\n"
        f"ID: {user_id}\n"
        f"Дата экзамена: {date_title or '—'}\n"
        f"Статус: {STATUS_ICON.get(status, '•')} {STATUS_TEXT.get(status, status)}\n"
        f"Подтвердил: {confirmed_by_name or '—'}\n"
        f"Создана: {fmt_dt(created_at)}"
    )

    rows = []
    if status != db.CANCELLED:
        rows.append([InlineKeyboardButton(
            text="❌ Отменить запись", callback_data=f"a:bc:{booking_id}"
        )])
    rows.append([back_button(f"a:bk:{date_id}:0", "⬅️ К списку")])

    await show(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    return True


@router.callback_query(F.data.startswith("a:b:"))
async def booking_detail(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    if await render_booking_detail(callback, booking_id):
        await callback.answer()
    else:
        await callback.answer("Заявка не найдена.", show_alert=True)


@router.callback_query(F.data.startswith("a:bc:"))
async def booking_cancel_confirm(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    row = await db.get_booking(booking_id)
    if not row:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    full_name, date_title = row[2], row[8]

    await show(
        callback,
        f"❌ Отменить заявку №{booking_id}?\n\n"
        f"Клиент: {full_name or '—'}\n"
        f"Дата: {date_title or '—'}\n\n"
        "Место освободится, клиент получит уведомление.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Да, отменить", callback_data=f"a:bc1:{booking_id}"
            )],
            [back_button(f"a:b:{booking_id}", "⬅️ Отмена")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("a:bc1:"))
async def booking_cancel_do(callback: CallbackQuery, bot: Bot):
    booking_id = int(callback.data.split(":")[2])
    changed, user_id = await db.cancel_booking(booking_id)

    if user_id is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if not changed:
        await callback.answer("Заявка уже была отменена.", show_alert=True)
        await render_booking_detail(callback, booking_id)
        return

    await callback.answer("Запись отменена")

    # Язык клиента, а не админа, который нажал кнопку.
    client_lang = texts.lang_or_default(await db.get_user_lang(user_id))
    try:
        await bot.send_message(user_id, texts.t("booking_cancelled", client_lang))
    except Exception as e:
        print(f"[client] не удалось уведомить {user_id} об отмене: {e}")
        await callback.message.answer(f"⚠️ Клиенту не доставлено уведомление: {e}")

    await render_booking_detail(callback, booking_id)


# ---------- СТАТИСТИКА ----------

@router.callback_query(F.data == "a:stats")
async def stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    data = await db.get_stats()
    dates = await db.get_dates_overview()

    lines = [
        "📊 Статистика",
        "",
        f"Дат всего: {data['dates_total']} (активных: {data['dates_active']})",
        f"Заявок всего: {data['total']}",
        f"✅ Подтверждено: {data['confirmed']}",
        f"⏳ Ждут подтверждения: {data['pending']}",
        f"❌ Отменено: {data['cancelled']}",
    ]

    if dates:
        lines += ["", "По датам:"]
        for _, title, seats_limit, is_active, confirmed, pending in dates:
            taken = confirmed + pending
            seats = f"{taken}/{seats_limit}" if seats_limit else str(taken)
            mark = "" if is_active else " (скрыта)"
            lines.append(f"• {title}{mark}: {seats}  ✅{confirmed} ⏳{pending}")

    await show(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Экспорт в Excel", callback_data="a:export")],
        [back_button("a:menu", "⬅️ В меню")],
    ]))
    await callback.answer()


# ---------- ЭКСПОРТ ----------

async def build_workbook() -> bytes:
    rows = await db.get_export_rows()
    dates = await db.get_dates_overview()

    wb = Workbook()

    ws = wb.active
    ws.title = "Записи"
    headers = ["№", "Дата экзамена", "ФИО", "Username", "Telegram ID",
               "Статус", "Подтвердил", "Создана (Ташкент)"]
    ws.append(headers)
    for booking_id, date_title, full_name, username, user_id, status, confirmed_by, created_at in rows:
        ws.append([
            booking_id,
            date_title or "—",
            full_name or "—",
            f"@{username}" if username else "—",
            user_id,
            STATUS_TEXT.get(status, status),
            confirmed_by or "—",
            fmt_dt(created_at),
        ])

    ws2 = wb.create_sheet("По датам")
    headers2 = ["Дата", "Лимит мест", "Подтверждено", "Ждут подтверждения",
                "Занято", "Свободно", "Активна"]
    ws2.append(headers2)
    for _, title, seats_limit, is_active, confirmed, pending in dates:
        taken = confirmed + pending
        ws2.append([
            title,
            seats_limit or "без лимита",
            confirmed,
            pending,
            taken,
            max(seats_limit - taken, 0) if seats_limit else "—",
            "да" if is_active else "нет",
        ])

    for sheet, header_row in ((ws, headers), (ws2, headers2)):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for i, name in enumerate(header_row, start=1):
            width = max(len(name) + 2, 12)
            for cell in sheet[get_column_letter(i)][1:]:
                width = max(width, min(len(str(cell.value or "")) + 2, 40))
            sheet.column_dimensions[get_column_letter(i)].width = width

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@router.callback_query(F.data == "a:export")
async def export_excel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Готовлю файл…")

    payload = await build_workbook()
    filename = f"zapisi_{datetime.now(config.TZ):%Y-%m-%d_%H-%M}.xlsx"

    await callback.message.answer_document(
        BufferedInputFile(payload, filename=filename),
        caption="📥 Выгрузка записей",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [back_button("a:menu", "⬅️ В меню")]
        ]),
    )
