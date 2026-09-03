import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat

import config
import handlers
from db import db_init
from storage import SQLiteStorage


async def set_admin_commands(bot: Bot):
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                [
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
    dp = Dispatcher(storage=SQLiteStorage(config.DB_PATH))
    handlers.setup(dp)
    await set_admin_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
