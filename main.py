import asyncio
import logging

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


async def main():
    config.validate()

    # база поднимается раньше диспетчера: в ней же лежит хранилище FSM
    await db_init()

    bot = Bot(token=config.TOKEN)
    dp = Dispatcher(storage=SQLiteStorage())
    handlers.setup(dp)
    await set_commands(bot)

    # фоновая рассылка напоминаний за день до экзамена
    asyncio.create_task(reminder_loop(bot))

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
