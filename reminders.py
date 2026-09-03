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
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

import config
import db
import texts

log = logging.getLogger(__name__)

CHECK_EVERY = 3600
SEND_FROM_HOUR = 9
SEND_TO_HOUR = 21


async def send_due_reminders(bot: Bot) -> int:
    """Шлёт напоминания на завтрашние экзамены. Возвращает число отправленных."""
    tomorrow = (db.today() + timedelta(days=1)).isoformat()
    due = await db.get_bookings_to_remind(tomorrow)

    sent = 0
    for booking_id, user_id, title in due:
        lang = texts.lang_or_default(await db.get_user_lang(user_id))
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


async def reminder_loop(bot: Bot):
    while True:
        try:
            if SEND_FROM_HOUR <= datetime.now(config.TZ).hour < SEND_TO_HOUR:
                await send_due_reminders(bot)
        except Exception:
            log.exception("сбой в цикле напоминаний")
        await asyncio.sleep(CHECK_EVERY)
