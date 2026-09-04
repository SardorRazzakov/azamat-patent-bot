"""Фоновая рассылка напоминаний за день до экзамена.

Одна реплика, long polling — планировщик не нужен, хватает asyncio-цикла.
Раз в час проверяем, у кого экзамен завтра, и шлём напоминание тем, кому
ещё не слали (reminder_sent_at). Колонка защищает от повторов при
перезапуске, поэтому цикл можно будить как угодно часто.

Не беспокоим клиентов ночью: рассылка идёт только с 9 до 21 по Ташкенту.
Если бот простоял весь вечер, напоминание уйдёт утром в день экзамена —
это хуже, чем накануне, но лучше, чем ничего.
"""

import asyncio
import logging
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import db
import texts

log = logging.getLogger(__name__)

CHECK_EVERY = 3600
SEND_FROM_HOUR = 9
SEND_TO_HOUR = 21

# Через сколько молчания считаем запись брошенной
ABANDON_AFTER_HOURS = 24


async def send_due_reminders(bot: Bot) -> int:
    """Шлёт напоминания на завтрашние экзамены. Возвращает число отправленных."""
    tomorrow = (db.today() + timedelta(days=1)).isoformat()
    due = await db.get_bookings_to_remind(tomorrow)
    langs = await db.get_user_langs([user_id for _, user_id, _ in due])

    sent = 0
    for booking_id, user_id, title in due:
        lang = texts.lang_or_default(langs.get(user_id))
        try:
            await bot.send_message(
                user_id, texts.t("exam_reminder", lang, title=title)
            )
        except TelegramForbiddenError:
            log.warning("напоминание: клиент %s заблокировал бота", user_id)
            await db.mark_reminded(booking_id)  # повторять бессмысленно
            continue
        except Exception as e:
            log.warning("напоминание по заявке %s не доставлено: %s", booking_id, e)
            continue

        # адрес — бонусом, без него напоминание уже отправлено
        with suppress(Exception):
            await bot.send_location(
                user_id,
                latitude=config.EXAM_LOCATION_LAT,
                longitude=config.EXAM_LOCATION_LON,
            )
        await db.mark_reminded(booking_id)
        sent += 1

    if sent:
        log.info("напоминаний отправлено: %d", sent)
    return sent


def continue_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Та же кнопка, что и в диалоге: ведёт к выбору даты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=texts.t("btn_continue", lang), callback_data="go:dates"
        )
    ]])


async def send_abandoned_nudges(bot: Bot) -> int:
    """Одно сообщение тем, кто начал запись и пропал. Второй раз — никогда."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(hours=ABANDON_AFTER_HOURS)).isoformat()
    users = await db.get_abandoned_users(cutoff)
    langs = await db.get_user_langs(users)

    sent = 0
    for user_id in users:
        lang = texts.lang_or_default(langs.get(user_id))
        try:
            await bot.send_message(
                user_id,
                texts.t("abandoned_nudge", lang),
                reply_markup=continue_keyboard(lang),
            )
            sent += 1
        except Exception as e:
            # флаг ставим в любом случае: повторять бессмысленно
            log.warning("возврат: %s не доставлено: %s", user_id, e)
        await db.mark_nudged(user_id)

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
        try:
            await bot.send_message(
                user_id,
                texts.t(
                    "cert_renewal", lang,
                    title=exam.strftime("%d.%m.%Y"),
                    expires=expires.strftime("%d.%m.%Y"),
                ),
                reply_markup=continue_keyboard(lang),
            )
            sent += 1
        except Exception as e:
            log.warning("продление: заявка %s не доставлена: %s", booking_id, e)
        await db.mark_cert_reminded(booking_id)

    if sent:
        log.info("напоминаний о продлении: %d", sent)
    return sent


async def reminder_loop(bot: Bot):
    while True:
        try:
            if SEND_FROM_HOUR <= datetime.now(config.TZ).hour < SEND_TO_HOUR:
                await send_due_reminders(bot)
                await send_abandoned_nudges(bot)
                await send_cert_renewals(bot)
        except Exception:
            log.exception("сбой в цикле напоминаний")
        await asyncio.sleep(CHECK_EVERY)
