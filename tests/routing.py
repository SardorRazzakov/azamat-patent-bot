"""Маршрутизация callback_data. Запуск: python tests/routing.py

Разбор идёт через F.data.startswith(), поэтому префиксы нельзя выбирать
наугад: если новый окажется началом чужого и встанет раньше, чужие апдейты
молча уйдут не в тот хендлер. Ошибка не падает и не логируется — кнопка
просто начинает делать не то.

Две части:

1. Статическая. Префиксы вынимаются из декораторов через AST, проверяется,
   что ни один не затеняет объявленный ниже. Новый хендлер попадает под
   проверку сам, без правки этого файла.

2. Поведенческая. Таблица «callback_data -> имя хендлера» прогоняется через
   настоящие фильтры aiogram, отдельно от имени админа и постороннего.
   Сами хендлеры не вызываются: проверяется адресация, а не работа.
"""

import ast
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="patentbot-routing-"), "r.db"
)
os.environ.setdefault(
    "BOT_TOKEN", "123456789:AAEhBOweik6ad9RpLZ8FzZzZzZzZzZzZzZzQQQQ"
)
os.environ["ADMIN_IDS"] = "777"

from aiogram import Dispatcher  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, User  # noqa: E402

import handlers  # noqa: E402

ADMIN_ID = 777
STRANGER_ID = 12345


# ---------- 1. СТАТИЧЕСКАЯ ПРОВЕРКА ЗАТЕНЕНИЯ ----------

def declared_callbacks(path: Path) -> list[tuple[str, str, str]]:
    """[(вид, значение, имя хендлера)] в порядке объявления в файле.

    Вид: prefix для startswith(...), exact для сравнения на равенство.
    """
    out = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            target = dec.func
            if not (isinstance(target, ast.Attribute)
                    and target.attr == "callback_query"):
                continue
            for arg in dec.args:
                if (isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Attribute)
                        and arg.func.attr == "startswith"
                        and arg.args
                        and isinstance(arg.args[0], ast.Constant)):
                    out.append(("prefix", arg.args[0].value, node.name))
                elif (isinstance(arg, ast.Compare)
                      and len(arg.ops) == 1
                      and isinstance(arg.ops[0], ast.Eq)
                      and isinstance(arg.comparators[0], ast.Constant)):
                    out.append(("exact", arg.comparators[0].value, node.name))
    return out


def check_shadowing() -> list[str]:
    """Префикс, объявленный раньше, не должен перехватывать чужие значения.

    Роутеры идут в порядке подключения, админский первым: его префикс
    способен перехватить клиентский callback у админа.
    """
    admin = declared_callbacks(ROOT / "handlers" / "admin.py")
    client = declared_callbacks(ROOT / "handlers" / "client.py")
    ordered = ([("admin", *row) for row in admin]
               + [("client", *row) for row in client])

    bad = []
    for i, (router_i, kind_i, value_i, name_i) in enumerate(ordered):
        if kind_i != "prefix":
            continue
        for router_j, kind_j, value_j, name_j in ordered[i + 1:]:
            if value_j.startswith(value_i):
                bad.append(
                    f"{router_i}.{name_i} с префиксом {value_i} перехватит "
                    f"{value_j} у {router_j}.{name_j} — тот объявлен ниже "
                    f"и своих апдейтов не увидит"
                )
    return bad


# ---------- 2. ПОВЕДЕНЧЕСКАЯ ПРОВЕРКА ----------

def make_callback(data: str, user_id: int) -> CallbackQuery:
    user = User(id=user_id, is_bot=False, first_name="Тест")
    chat = Chat(id=user_id, type="private")
    return CallbackQuery(
        id="1",
        from_user=user,
        chat_instance="1",
        data=data,
        message=Message(message_id=1, date=0, chat=chat, from_user=user),
    )


async def resolve(router, event) -> str | None:
    """Имя хендлера, которому достался бы апдейт. Хендлер не вызывается."""
    observer = router.callback_query

    ok, data = await observer.check_root_filters(event)
    if not ok:
        return None

    for handler in observer.handlers:
        matched, _ = await handler.check(event, **data)
        if matched:
            return handler.callback.__name__

    for sub in router.sub_routers:
        found = await resolve(sub, event)
        if found:
            return found
    return None


# callback_data -> кто должен его получить.
ADMIN_ROUTES = {
    "a:menu": "admin_menu",
    "a:dates": "dates_list",
    "a:dhid": "hidden_dates_list",
    "a:d:7": "date_detail",
    "a:dadd": "date_add_start",
    "a:dbulk": "dates_bulk_start",
    "a:ddate:7": "date_value_start",
    "a:dlim:7": "date_limit_start",
    "a:dren:7": "date_rename_start",
    "a:ddel:7": "date_delete_confirm",
    "a:ddel1:7": "date_delete_do",
    "a:drst:7": "date_restore",
    "a:bdates": "bookings_dates",
    "a:bk:7:0": "bookings_list",
    "a:b:7": "booking_detail",
    "a:bdoc:7": "booking_documents",
    "a:bo:7:passed": "booking_outcome",
    "a:bc:7": "booking_cancel_confirm",
    "a:bc1:7": "booking_cancel_do",
    "a:bcast:7": "broadcast_start",
    "a:bcast1:7": "broadcast_send",
    "a:sr": "search_start",
    "a:stats": "stats",
    "a:fn:today": "funnel",
    "a:export": "export_excel",
    "a:nudgeoff": "suppress_nudges",
}

# Клиентские кнопки: у админа они работают так же — админский роутер их
# не разбирает, и они проваливаются дальше.
CLIENT_ROUTES = {
    "lang:ru": "language_chosen",
    "faq": "faq_root",
    "faq:s:exam": "faq_section",
    "faq:q:price": "faq_answer",
    "go:dates": "show_dates",
    "go:more": "add_more_start",
    "date_7": "date_chosen",
    "noop": "noop_handler",
    # Кнопку жмёт админ, но живёт она в клиентском роутере: доступ
    # проверяется внутри самого хендлера, а не фильтром роутера.
    "confirm_7": "confirm_payment",
}


async def check_routes(dp) -> list[str]:
    bad = []

    for data, expected in {**ADMIN_ROUTES, **CLIENT_ROUTES}.items():
        got = await resolve(dp, make_callback(data, ADMIN_ID))
        if got != expected:
            bad.append(f"админ, {data}: попал в {got}, ожидался {expected}")

    # Посторонний: админские кнопки не должны доходить ни до кого.
    for data in ADMIN_ROUTES:
        got = await resolve(dp, make_callback(data, STRANGER_ID))
        if got is not None:
            bad.append(f"посторонний, {data}: утёк в {got}, ожидалось «никто»")

    for data, expected in CLIENT_ROUTES.items():
        got = await resolve(dp, make_callback(data, STRANGER_ID))
        if got != expected:
            bad.append(f"посторонний, {data}: попал в {got}, ожидался {expected}")

    return bad


# ---------- ЗАПУСК ----------

async def main() -> int:
    failed = 0

    shadowing = check_shadowing()
    if shadowing:
        failed += 1
        print("FAIL  затенение префиксов")
        for line in shadowing:
            print(f"        {line}")
    else:
        print("ok    затенение префиксов")

    dp = Dispatcher()
    handlers.setup(dp)

    routes = await check_routes(dp)
    if routes:
        failed += 1
        print("FAIL  адресация callback_data")
        for line in routes:
            print(f"        {line}")
    else:
        n = len(ADMIN_ROUTES) + len(CLIENT_ROUTES)
        print(f"ok    адресация callback_data "
              f"({n} кнопок, админ и посторонний)")

    print()
    print("маршрутизация в порядке" if not failed
          else f"провалено проверок: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
