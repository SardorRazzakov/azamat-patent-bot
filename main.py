import asyncio
import logging
from contextlib import AsyncExitStack, suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat

import config
import handlers
import db
from db import db_init
from reminders import reminder_loop
from storage import SQLiteStorage


async def set_commands(bot: Bot):
    # видно всем клиентам
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать / сменить язык"),
            BotCommand(command="faq", description="Частые вопросы"),
        ])
    except Exception as e:
        print(f"[commands] не удалось задать общие команды: {e}")

    # админам — свои, поверх общих
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Начать / сменить язык"),
                    BotCommand(command="faq", description="Частые вопросы"),
                    BotCommand(command="admin", description="Админ-панель"),
                    BotCommand(command="cancel", description="Отменить текущее действие"),
                ],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as e:
            print(f"[admins] не удалось задать команды для {admin_id}: {e}")


async def stop_task(task: asyncio.Task):
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def main():
    config.validate()

    # Каждый ресурс регистрирует свою уборку сразу после захвата, поэтому
    # закрывается всё и на штатной остановке, и на Ctrl+C, и на исключении
    # посреди старта. Для базы это обязательно: рабочий поток aiosqlite не
    # демон, и с незакрытым соединением процесс не упадёт, а повиснет.
    async with AsyncExitStack() as stack:
        # Регистрируем до db_init(): соединение открывается внутри него,
        # и упасть он может уже с открытым — например на миграции.
        # База поднимается раньше диспетчера: в ней же лежит хранилище FSM.
        stack.push_async_callback(db.close)
        await db_init()

        bot = Bot(token=config.TOKEN)
        # HTTP-сессия живёт отдельно от диспетчера и сама не закрывается
        stack.push_async_callback(bot.session.close)

        dp = Dispatcher(storage=SQLiteStorage())
        handlers.setup(dp)
        await set_commands(bot)

        # Фоновая рассылка напоминаний за день до экзамена.
        # Ссылку держим у себя: у задачи без единой ссылки на неё event loop
        # хранит только слабую, и сборщик вправе убрать её посреди работы.
        background = asyncio.create_task(reminder_loop(bot))
        stack.push_async_callback(stop_task, background)

        await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
