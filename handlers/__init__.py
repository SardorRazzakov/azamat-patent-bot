from aiogram import Dispatcher

from . import admin, client


def setup(dp: Dispatcher):
    """Админка идёт первой: её роутер отфильтрован по ADMIN_IDS,
    остальное падает дальше в клиентский роутер."""
    dp.include_router(admin.router)
    dp.include_router(client.router)


__all__ = ["admin", "client", "setup"]
