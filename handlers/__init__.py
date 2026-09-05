from aiogram import Dispatcher

from . import admin, business, client


def setup(dp: Dispatcher):
    """Админка идёт первой: её роутер отфильтрован по ADMIN_IDS,
    остальное падает дальше в клиентский роутер.

    Business-роутер разбирает только business_message и business_connection —
    отдельные типы апдейтов, с обычными сообщениями он не пересекается,
    поэтому его место в цепочке ни на что не влияет."""
    dp.include_router(admin.router)
    dp.include_router(business.router)
    dp.include_router(client.router)


__all__ = ["admin", "business", "client", "setup"]
