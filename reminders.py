"""Фоновые рассылки и суточный бэкап базы.

Одна реплика, long polling — планировщик не нужен, хватает asyncio-цикла.
Цикл просыпается раз в час; от повторов защищают флаги в базе, поэтому
будить его можно как угодно часто.

Клиентам не пишем ночью: рассылки идут только с 9 до 21 по Ташкенту.
Если бот простоял весь вечер, напоминание уйдёт утром — хуже, чем
накануне, но лучше, чем ничего.
"""

import asyncio
import logging
import os
import sqlite3
import tempfile
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import config
import db
import texts

log = logging.getLogger(__name__)

CHECK_EVERY = 3600
SEND_FROM_HOUR = 9
SEND_TO_HOUR = 21

# Через сколько молчания считаем запись брошенной
ABANDON_AFTER_HOURS = 24

# Пауза между отправками: Telegram режет бота примерно на 30 сообщениях
# в секунду, 40 мс держат нас чуть ниже порога.
SEND_PAUSE = 0.04

# Час по Ташкенту, начиная с которого можно снимать суточный бэкап
BACKUP_HOUR = 4
BACKUP_META_KEY = "last_backup_date"

# Итог попытки доставки
SENT = "sent"          # дошло
BLOCKED = "blocked"    # доставить нельзя никогда — флаг ставим
RETRY = "retry"        # временная помеха — флаг не ставим, повторим позже


def continue_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Та же кнопка, что и в диалоге: ведёт к выбору даты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=texts.t("btn_continue", lang), callback_data="go:dates"
        )
    ]])


async def deliver(bot: Bot, user_id: int, text: str, keyboard=None) -> str:
    """Одна отправка с разбором причины отказа.

    Возвращает SENT / BLOCKED / RETRY. Разница важна: за BLOCKED ставим флаг
    и больше не пытаемся, за RETRY — не ставим, иначе человек молча
    останется без сообщения из-за секундного сбоя.
    """
    try:
        await bot.send_message(user_id, text, reply_markup=keyboard)
        return SENT
    except TelegramRetryAfter as e:
        # 429: ждём ровно столько, сколько просит Telegram, чтобы остаток
        # пачки не разбился о тот же лимит. Сама заявка уйдёт в следующий цикл.
        log.warning("429 на %s: ждём %s c", user_id, e.retry_after)
        await asyncio.sleep(e.retry_after + 1)
        return RETRY
    except TelegramForbiddenError:
        log.info("клиент %s заблокировал бота", user_id)
        return BLOCKED
    except TelegramBadRequest as e:
        # чат не найден, аккаунт удалён — доставить нельзя в принципе
        log.info("доставка %s невозможна: %s", user_id, e)
        return BLOCKED
    except TelegramNetworkError as e:
        log.warning("сеть подвела на %s: %s", user_id, e)
        return RETRY
    except Exception as e:
        # Неизвестную ошибку считаем постоянной: иначе задача будет долбиться
        # в неё каждый час до скончания века.
        log.error("неожиданная ошибка доставки %s: %s", user_id, e)
        return BLOCKED


async def send_due_reminders(bot: Bot) -> int:
    """Напоминания о завтрашнем экзамене."""
    tomorrow = (db.today() + timedelta(days=1)).isoformat()
    due = await db.get_bookings_to_remind(tomorrow)
    langs = await db.get_user_langs([user_id for _, user_id, _ in due])

    sent = 0
    for booking_id, user_id, title in due:
        lang = texts.lang_or_default(langs.get(user_id))
        result = await deliver(bot, user_id, texts.t("exam_reminder", lang, title=title))

        if result == RETRY:
            continue
        if result == SENT:
            # адрес — бонусом, без него напоминание уже отправлено
            with suppress(Exception):
                await bot.send_location(
                    user_id,
                    latitude=config.EXAM_LOCATION_LAT,
                    longitude=config.EXAM_LOCATION_LON,
                )
            sent += 1
        await db.mark_reminded(booking_id)
        await asyncio.sleep(SEND_PAUSE)

    if sent:
        log.info("напоминаний о завтрашнем экзамене: %d", sent)
    return sent


async def send_abandoned_nudges(bot: Bot) -> int:
    """Одно сообщение тем, кто начал запись и пропал. Второй раз — никогда."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(hours=ABANDON_AFTER_HOURS)).isoformat()
    users = await db.get_abandoned_users(cutoff)
    langs = await db.get_user_langs(users)

    sent = 0
    for user_id in users:
        lang = texts.lang_or_default(langs.get(user_id))
        result = await deliver(
            bot, user_id, texts.t("abandoned_nudge", lang), continue_keyboard(lang)
        )

        if result == RETRY:
            continue
        if result == SENT:
            sent += 1
        await db.mark_nudged(user_id)
        await asyncio.sleep(SEND_PAUSE)

    if sent:
        log.info("сообщений о брошенной записи: %d", sent)
    return sent


async def send_cert_renewals(bot: Bot) -> int:
    """Напоминание тем, у кого сертификат истекает меньше чем через два месяца."""
    today_iso = db.today().isoformat()
    due = await db.get_cert_renewals(today_iso)
    langs = await db.get_user_langs([user_id for _, user_id, _ in due])

    sent = 0
    for booking_id, user_id, exam_date in due:
        lang = texts.lang_or_default(langs.get(user_id))
        exam = date.fromisoformat(exam_date)
        try:
            expires = exam.replace(year=exam.year + db.CERT_YEARS)
        except ValueError:
            # 29 февраля: через три года такого числа нет
            expires = exam.replace(year=exam.year + db.CERT_YEARS, day=28)

        result = await deliver(
            bot, user_id,
            texts.t(
                "cert_renewal", lang,
                title=exam.strftime("%d.%m.%Y"),
                expires=expires.strftime("%d.%m.%Y"),
            ),
            continue_keyboard(lang),
        )

        if result == RETRY:
            continue
        if result == SENT:
            sent += 1
        await db.mark_cert_reminded(booking_id)
        await asyncio.sleep(SEND_PAUSE)

    if sent:
        log.info("напоминаний о продлении: %d", sent)
    return sent


# ---------- БЭКАП ----------

def _snapshot(src_path: str) -> bytes:
    """Согласованный снимок работающей базы.

    Копировать файл на живой базе нельзя: при WAL часть данных лежит вне
    основного файла, и копия окажется битой. Встроенный backup API снимает
    целостный слепок, не мешая записи.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dst_path = os.path.join(tmp, "snapshot.db")
        src = sqlite3.connect(src_path)
        dst = sqlite3.connect(dst_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        with open(dst_path, "rb") as f:
            return f.read()


async def send_backup(bot: Bot) -> bool:
    """Шлёт снимок базы всем админам. True — дошло хотя бы до одного."""
    payload = await asyncio.get_running_loop().run_in_executor(
        None, _snapshot, config.DB_PATH
    )
    stamp = datetime.now(config.TZ).strftime("%Y-%m-%d_%H-%M")
    size_kb = round(len(payload) / 1024)

    delivered = False
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_document(
                admin_id,
                BufferedInputFile(payload, filename=f"backup_{stamp}.db"),
                caption=f"💾 Резервная копия базы · {stamp} · {size_kb} КБ",
            )
            delivered = True
        except Exception as e:
            log.warning("бэкап не доставлен админу %s: %s", admin_id, e)
        await asyncio.sleep(SEND_PAUSE)

    if delivered:
        log.info("бэкап отправлен, %d КБ", size_kb)
    return delivered


async def reminder_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(config.TZ)

            if SEND_FROM_HOUR <= now.hour < SEND_TO_HOUR:
                await send_due_reminders(bot)
                await send_abandoned_nudges(bot)
                await send_cert_renewals(bot)

            # дата последнего бэкапа лежит в базе, а не в памяти: иначе
            # каждый деплой присылал бы админам лишнюю копию
            if now.hour >= BACKUP_HOUR:
                today_iso = now.date().isoformat()
                if await db.get_meta(BACKUP_META_KEY) != today_iso:
                    if await send_backup(bot):
                        await db.set_meta(BACKUP_META_KEY, today_iso)
        except Exception:
            log.exception("сбой в фоновом цикле")
        await asyncio.sleep(CHECK_EVERY)
