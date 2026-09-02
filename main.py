import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

import config
import handlers
from db import db_init


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

    bot = Bot(token=config.TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    handlers.setup(dp)

    await db_init()
    await set_admin_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
