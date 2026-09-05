from aiogram import Dispatcher

from . import admin, business, client, group


def setup(dp: Dispatcher):
    """Групповой роутер идёт первым и отфильтрован по типу чата.

    Первым — потому что дальше в цепочке стоит админка, чьи FSM-шаги
    принимают любой текст без слэша: сообщение админа в группе попало бы
    в такой шаг. А в самом конце клиентский `@router.message()` без
    фильтров, который до этого отвечал в группе «Тушунмадим».

    Дальше админка: её роутер отфильтрован по ADMIN_IDS, остальное падает
    в клиентский.

    Business-роутер разбирает только business_message и business_connection —
    отдельные типы апдейтов, с обычными сообщениями он не пересекается,
    поэтому его место в цепочке ни на что не влияет."""
    dp.include_router(group.router)
    dp.include_router(admin.router)
    dp.include_router(business.router)
    dp.include_router(client.router)


__all__ = ["admin", "business", "client", "group", "setup"]
